# \*_Product Specification: AI-Mediated Objective Assessment System_

## **0\. Purpose and Non-Goals**

### **Purpose**

To assess **learner mastery of educational objectives** through structured, AI-mediated oral-style examinations grounded in educator-defined rubrics, with defensible grading and auditability.

### **Explicit Non-Goals**

- Not a full LMS replacement.
- Not primary instruction delivery.
- Not automated curriculum generation.
- Not adaptive pedagogy without teacher authorization.

This system is **assessment infrastructure**, not an AI tutor fantasy.

## **1\. Core Concepts and Terminology**

### **1.1 Learning Objective**

A discrete, assessable unit of understanding intended to be mastered over a short time window (e.g., one week).

Each Learning Objective consists of:

- **Objective Statement** (plain-language goal)
- **Scope Boundaries** (what is _not_ included)
- **Assessment Prompts** (initial \+ challenge prompts)
- **Rubric** (criteria for S/A/C/F)
- **Permissions** (e.g., extended discussion allowed)
- **Dependencies** (other objectives required first)

### **1.2 Objective Groupings**

Objectives are grouped into _strands_, which represent **semantic and pedagogical structure** above individual objectives.

### **1.3 Assessment Attempt**

A single learner’s interaction with the AI for a given objective, producing:

- Audio recording
- Transcript
- AI reasoning trace (internal, summarized)
- Grade (S/A/C/F)
- Confidence score
- Flags for educator review

## **2\. Key Actors**

### **2.1 Educator**

Authority over:

- Objective design
- Rubric definition
- Objective ordering and dependencies
- Assignment to learners
- Grade review and override

### **2.2 Learner**

Authority over:

- Initiating assessments
- Opting into permitted extensions
- Reviewing feedback (not raw rubric logic)

## **3\. Educator Workflows**

### **3.1 Define a New Learning Objective**

**Inputs**

- Objective Title
- Objective Description (learner-facing)
- Assessment Time Expectation (e.g., 10–15 min)
- Initial Assessment Prompts (open-ended)
- Challenge Prompts (used conditionally)
- Rubric (see §3.1.1)
- Extension Policy (Allowed / Disallowed / Conditional)
- Prerequisites (Objective IDs)

**System Behavior**

- Validate rubric completeness.
- Run rubric sanity checks (e.g., overlapping criteria).
- Generate preview assessment simulation (AI ↔ sample learner).

#### **3.1.1 Rubric Structure (Required)**

Each rubric criterion includes:

- Criterion Name
- Description
- Evidence Indicators (what _counts_)
- Failure Modes (common misconceptions)
- Grade Threshold Mapping (S/A/C/F)

Critique: Free-text rubrics without failure modes are pedagogically lazy and should be discouraged by UI friction.

### **3.2 Create and Manage Objective Groupings**

Educators may:

- Create Strands / Sequences
- Assign objectives to groupings
- Order objectives linearly or as DAGs
- Define dependency rules (hard vs. soft)

**Dependency Types**

- **Hard Gate**: Cannot attempt Objective C without passing A and B
- **Soft Gate**: Strongly recommended; warning shown to learner

### **3.3 Assign Objectives to Learners**

Assignments can be:

- Individual
- Group-based
- Conditional (e.g., assign remediation objective if grade ≤ C)

Educator defines:

- Availability window
- Number of allowed attempts
- Retake policy (immediate / delayed / manual approval)

### **3.4 Review Learner Assessment Results**

Educator can view:

- Transcript (annotated)
- AI-identified strengths and gaps
- Rubric mapping (criterion → evidence)
- Grade \+ confidence score
- Flags (e.g., gaming detected, uncertainty)

Educator actions:

- Accept grade
- Override grade (with reason)
- Assign follow-up objective
- Leave qualitative feedback

Critique: Override must be frictionless. Any system that fights teacher judgment will be abandoned.

## **4\. Learner Workflows**

### **4.1 View Learning Hierarchy**

Learner dashboard displays:

- Strand / Sequence tree
- Objectives with:
  - Status: Not Attempted / In Progress / Completed
  - Grade: S / A / C / F
  - Prerequisite locks
- Visual progression indicators

Grades should be:

- Visible
- Non-numeric
- De-emphasized relative to mastery state

### **4.2 Begin an Objective Assessment**

**Flow**

1. Learner selects an available objective
2. System presents:
   - Objective description
   - Time expectation
   - Permissions (e.g., extensions)
3. Learner confirms readiness
4. Audio capture begins
5. AI interlocutor initiates assessment

## **5\. AI-Mediated Assessment Flow (Critical)**

### **5.1 Interview Phases**

1. **Orientation**
   - AI explains format and expectations
   - Confirms consent to record
2. **Primary Prompts**
   - Educator-defined questions
   - Open-ended, non-leading
3. **Dynamic Probing**
   - Follow-ups triggered by:
     - Ambiguity
     - Inconsistency
     - Over-generalization
   - Includes misconception traps
4. **Optional Extension**
   - Only if permitted
   - Explicitly labeled as exploratory, not required
5. **Closure**
   - AI summarizes learner’s stated understanding
   - Learner can correct summary (important\!)

Critique: Summary correction is a crucial guardrail against AI misinterpretation.

### **5.2 Capture and Transcription Workflow**

**Audio Capture**

- Client-side recording (mobile/web)
- Chunked streaming to backend
- Redundant local buffering

**Transcription**

- Near-real-time ASR
- Timestamped utterances
- Confidence markers per segment

**Post-processing**

- Clean transcript
- Preserve hesitations, corrections (do _not_ over-sanitize)
- Align transcript to prompt structure

### **5.3 Evaluation Pipeline**

1. Transcript segmented by prompt
2. Evidence extracted per rubric criterion
3. Failure modes checked explicitly
4. Confidence score computed
5. Grade assigned
6. Flags generated (if any)

**Flags Examples**

- High fluency / low substance
- Repeated evasion
- Vocabulary mirroring without explanation
- Inconsistent reasoning

## **6\. Data Model (High-Level)**

These are concepts implied by the application's description, not necessarily a description of tables or classes.

- User (Educator / Learner)
- Objective
- ObjectiveGroup (Strand / Sequence)
- Dependency
- Assignment
- AssessmentAttempt
- TranscriptSegment
- RubricCriterion
- EvaluationResult
- EducatorOverride

All assessment artifacts must be immutable once finalized (except via override).

## **7\. Trust, Auditability, and Risk Controls**

### **Required**

- Full transcript retention
- Rubric-to-evidence traceability
- Educator override history
- Confidence indicators surfaced

### **Explicitly Avoid**

- Black-box grades
- Auto-promotion without review
- Hidden AI prompt logic

## **8\. Known Weaknesses (Design Acknowledgment)**

- Oral assessment biases verbal thinkers
- LLM judgment is probabilistic, not authoritative
- Rubric quality bounds system quality

These should be acknowledged in documentation, not buried.

## **9\. MVP Scope Recommendation**

**Include**

- Single subject
- Linear sequences
- Single-attempt assessments
- Manual educator review

**Exclude (for now)**

- Cross-objective analytics
- Automated remediation
- Parent dashboards
- Generative instruction

## **10\. Final Critique**

This spec is viable _only if_ you resist:

- turning it into an LMS,
- inflating AI autonomy,
- hiding uncertainty for the sake of polish.

If implemented faithfully, this is a **serious assessment instrument**, not edtech noise.

## **11\. Implementation Recommendations**

- Use LangChain/LangGraph to model agents and agent state.
- Use the OpenAI GPT language model, at first, to implement most of the LLM operations. However, design the system
  so that choice of language model for various tasks is configurable via the application's configuration system.
