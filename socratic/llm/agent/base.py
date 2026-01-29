"""Base agent class for async LangGraph agents.

Provides a fixed graph topology with customizable extension points,
modeled after the Propel BaseAgent pattern but adapted for async
execution and streaming.
"""

from __future__ import annotations

import logging
import typing as t

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from .state import AgentState

logger = logging.getLogger(__name__)

TState = t.TypeVar("TState", bound=AgentState)


class BaseAgent(t.Generic[TState]):
    """Base class for LangGraph-based agents.

    Establishes a fixed graph topology::

        start → status → model → tool → status → model → ... → end

    Subclasses customize behavior by overriding extension points rather than
    rewiring the graph:

    - ``system_prompt(state)`` — static system message (required)
    - ``update_status(state)`` — dynamic status rendered each turn
    - ``exit(state)`` — termination predicate
    - ``tool_list(state)`` — available tools

    The model node constructs its input as::

        [system_prompt] + messages + [status]

    This gives the LLM the static instructions, conversation history, and a
    fresh snapshot of the current situation on every call.
    """

    name: str

    def __init__(
        self,
        model: BaseChatModel,
        *,
        tools: t.Sequence[BaseTool] | None = None,
    ) -> None:
        self.model = model
        self.tools: dict[str, BaseTool] = {tool.name: tool for tool in (tools or [])}

        for base in getattr(type(self), "__orig_bases__", ()):
            args = t.get_args(base)
            if args and not isinstance(args[0], t.TypeVar):
                state_schema = args[0]
                break
        else:
            raise TypeError(f"{type(self).__name__} must parameterize BaseAgent[TState]")

        self._graph = StateGraph(state_schema)
        self._wire_graph()

    def _node_name(self, name: str) -> str:
        """Return a scoped node name, prefixed with the agent name if set."""
        return f"{self.name}.{name}" if self.name else name

    def _wire_graph(self) -> None:
        """Build the fixed graph topology."""
        nn = self._node_name

        self._graph.add_node(nn("start"), self._start)
        self._graph.set_entry_point(nn("start"))

        self._graph.add_node(nn("status"), self._status)
        self._graph.add_edge(nn("start"), nn("status"))

        self._graph.add_node(nn("model"), self._call_model)
        self._graph.add_edge(nn("status"), nn("model"))
        self._graph.add_conditional_edges(nn("model"), self._post_model, [nn("tool"), nn("end")])

        self._graph.add_node(nn("tool"), self._tool_node)
        self._graph.add_conditional_edges(nn("tool"), self._should_exit, [nn("status"), nn("end")])

        self._graph.add_node(nn("end"), self._end)
        self._graph.set_finish_point(nn("end"))

    def compile(self, **kwargs: t.Any) -> t.Any:
        """Compile the graph for execution."""
        return self._graph.compile(**kwargs)

    # -- Extension points (override in subclasses) -------------------------

    def system_prompt(self, state: TState) -> SystemMessage:
        """Return the static system message for this agent.

        Must be overridden by subclasses.
        """
        raise NotImplementedError

    def update_status(self, state: TState) -> dict[str, t.Any]:
        """Return a state update dict with a fresh ``status`` message.

        Called before every model invocation. Override to render a dynamic
        status message that gives the model situational awareness.

        Returns:
            Dict with at least ``{"status": HumanMessage(...)}``, or empty
            dict if no status is needed.
        """
        return {}

    def exit(self, state: TState) -> bool:
        """Return True if the agent should terminate.

        Checked after tool execution. If True, the agent stops without
        calling the model again. Override to implement domain-specific
        termination logic.
        """
        return state.completed

    def before_work(self, state: TState) -> dict[str, t.Any]:
        """Hook called at the start of graph execution.

        Override to perform initialization or state augmentation.
        """
        return {}

    def after_work(self, state: TState) -> dict[str, t.Any]:
        """Hook called at the end of graph execution.

        Override to perform cleanup or result extraction.
        """
        return {}

    def tool_list(self, state: TState | None = None) -> list[BaseTool]:
        """Return the tools available to the model.

        Override to dynamically adjust tools based on state.
        """
        return list(self.tools.values())

    # -- Internal graph nodes ----------------------------------------------

    async def _start(self, state: TState) -> dict[str, t.Any]:
        return self.before_work(state)

    async def _status(self, state: TState) -> dict[str, t.Any]:
        return self.update_status(state)

    async def _call_model(self, state: TState, config: t.Any) -> dict[str, t.Any]:
        """Call the LLM with system prompt + history + status."""
        sendlist: list[BaseMessage] = [self.system_prompt(state)]
        sendlist.extend(state.messages)
        if state.status is not None:
            sendlist.append(state.status)

        tools = self.tool_list(state)
        runnable = self.model.bind_tools(tools) if tools else self.model
        response = await runnable.ainvoke(sendlist, config=config)

        return {"messages": [response]}

    def _post_model(self, state: TState) -> str:
        """Route after model: to tools if tool calls, else end the turn."""
        last_ai = next(
            (m for m in reversed(state.messages) if isinstance(m, AIMessage)),
            None,
        )
        if last_ai is not None and last_ai.tool_calls:
            return self._node_name("tool")
        return self._node_name("end")

    async def _tool_node(self, state: TState) -> dict[str, t.Any]:
        """Execute pending tool calls."""
        tools = self.tool_list(state)
        node = ToolNode(tools)
        return await node.ainvoke(state)  # pyright: ignore[reportUnknownMemberType]

    def _should_exit(self, state: TState) -> str:
        """After tools: exit if done, otherwise loop back to status → model."""
        if self.exit(state):
            return self._node_name("end")
        return self._node_name("status")

    async def _end(self, state: TState) -> dict[str, t.Any]:
        return self.after_work(state)
