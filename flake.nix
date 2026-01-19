{
  description = "Socratic";

  inputs = {
    devshell = {
      url = "github:numtide/devshell";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nixpkgs.url = "nixpkgs";
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    process-compose.url = "github:jessedhillon/process-compose/jessedhillon/fix-process-ports";
  };

  outputs =
    {
      nixpkgs,
      treefmt-nix,
      ...
    }@inputs:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
        overlays = [
          inputs.devshell.overlays.default
          inputs.process-compose.overlays.default
        ];
      };
      treefmtEval = treefmt-nix.lib.evalModule pkgs {
        projectRootFile = "flake.nix";
        programs = {
          nixfmt.enable = true;
          prettier.enable = true;
        };
        settings.formatter.python = {
          command = "${pkgs.bash}/bin/bash";
          options = [
            "-euc"
            ''
              ${pkgs.ruff}/bin/ruff format -q "$@" && ${pkgs.isort}/bin/isort -q --dt "$@"
            ''
            "--"
          ];
          includes = [ "*.py" ];
          excludes = [ "*/typings/*" ];
        };
      };
    in
    {
      formatter.${system} = treefmtEval.config.build.wrapper;
      checks.${system}.formatting = treefmtEval.config.build.check inputs.self;

      devShells.${system}.default = pkgs.devshell.mkShell {
        name = "socratic";
        motd = "{32}Socratic activated{reset}\n$(type -p menu &>/dev/null && menu)\n";

        env = [
          {
            name = "CLAUDE_CONFIG_DIR";
            eval = "$PRJ_ROOT/.claude";
          }
          {
            name = "XDG_STATE_HOME";
            eval = "$PRJ_ROOT/.state";
          }
          {
            name = "PGDATA";
            eval = "$XDG_STATE_HOME/postgresql";
          }
          {
            name = "PGHOST";
            eval = "$XDG_STATE_HOME";
          }
          {
            name = "REDIS_SOCKET_PATH";
            eval = "$XDG_STATE_HOME/redis/redis.sock";
          }
          {
            name = "RABBITMQ_NODENAME";
            value = "rabbit@localhost";
          }
          {
            name = "RABBITMQ_NODE_PORT";
            value = "5632";
          }
          {
            name = "RABBITMQ_HOME";
            eval = "$XDG_STATE_HOME/$RABBITMQ_NODENAME";
          }
          {
            name = "RABBITMQ_MNESIA_BASE";
            eval = "$RABBITMQ_HOME/mnesia";
          }
          {
            name = "RABBITMQ_LOGS";
            eval = "$RABBITMQ_HOME/logs";
          }
          {
            name = "RABBITMQ_PID_FILE";
            eval = "$XDG_STATE_HOME/$RABBITMQ_NODENAME.pid";
          }
          {
            name = "PYTHONBREAKPOINT";
            value = "jdbpp.set_trace";
          }
          {
            name = "PYTHON_BASIC_REPL";
            value = "1";
          }
          {
            name = "PRE_COMMIT_HOME";
            eval = "$PRJ_ROOT/.cache/pre-commit";
          }
        ];

        devshell.startup.create-dirs.text = ''
          mkdir -p "$RABBITMQ_HOME" "$RABBITMQ_MNESIA_BASE" "$(dirname "$RABBITMQ_LOGS")" "$XDG_STATE_HOME/redis" "$XDG_STATE_HOME/remote-profile"
        '';

        packages = with pkgs; [
          bubblewrap
          claude-code
          fzf
          gh
          isort
          poetry
          postgresql_17
          pre-commit
          process-compose
          pyright
          python313
          nodejs
          redis
          ruff
          uv
          yq
        ];

        commands = [
          {
            name = "sandbox-claude";
            command = ''
              GIT_SSH_COMMAND='ssh -F /dev/null -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519' \
              bwrap --bind / / \
              --remount-ro / \
              --ro-bind /nix /nix \
              --bind "$(pwd)" "$(pwd)" \
              --bind "/home/jesse/.cache" "/home/jesse/.cache" \
              --bind "/home/jesse/.ansible" "/home/jesse/.ansible" \
              --bind "/home/jesse/.npm" "/home/jesse/.npm" \
              --chdir "$(pwd)" \
              --proc /proc \
              --dev /dev \
              --tmpfs /tmp \
              -- \
              claude --dangerously-skip-permissions'';
          }
          {
            name = "install-hooks";
            command = ''
              if [[ -f ".pre-commit-config.yaml" ]]; then
                pushd $PRJ_ROOT
                pre-commit install --overwrite --install-hooks
                popd
              fi
            '';
            help = "install or update pre-commit hooks";
          }
          {
            name = "generate-api-clients";
            command = ''
              if [[ -z "''${1:-}" ]]; then
                echo "A web application name must be specified, example: generate-api-clients socratic" >&2
                exit 1
              fi
              set -euo pipefail
              SERVER_PIDS=()
              APP_NAME=$1
              STARTED_SERVER=false

              # Get the expected port from config
              API_PORT=$(yq -r ".$APP_NAME.backend.port" "$PRJ_ROOT/config/web.yaml")
              if [[ -z "$API_PORT" || "$API_PORT" == "null" ]]; then
                echo "Could not find backend port for $APP_NAME in config/web.yaml" >&2
                exit 1
              fi

              cleanup() {
                if [[ "$STARTED_SERVER" == "true" ]]; then
                  echo "Stopping API server..."
                  for pid in "''${SERVER_PIDS[@]}"; do
                    kill "$pid" 2>/dev/null || true
                  done
                fi
              }
              trap cleanup EXIT

              # Check if something is already listening on the port
              if ss -tln | grep -q ":$API_PORT "; then
                echo "Server already running on port $API_PORT, skipping backend startup..."
              else
                echo "Starting $APP_NAME API server on port $API_PORT..."
                poetry run python -m socratic.cli web serve $APP_NAME &
                SERVER_PIDS+=($!)
                STARTED_SERVER=true
                sleep 3
              fi

              echo "Generating API client for $APP_NAME..."
              pushd $PRJ_ROOT/socratic/web/$APP_NAME/frontend > /dev/null
              npx openapi-ts
              popd > /dev/null

              echo "$APP_NAME API clients generated successfully"
            '';
            help = "generate TypeScript API clients from OpenAPI specs";
          }
          {
            name = "debug-browser";
            command = "google-chrome-stable --remote-debugging-port=9222 --user-data-dir=$XDG_STATE_HOME/remote-profile > $XDG_STATE_HOME/chrome.log 2>&1 &";
            help = "launch an instance of Chrome with remote-debugging enabled on 9222";
          }
          {
            name = "dev";
            command = "process-compose up";
            help = "start development services";
          }
          {
            name = "copy-creds";
            command = ''
              set -euo pipefail
              CREDS_FILE="$PRJ_ROOT/.credentials"
              if [[ ! -f "$CREDS_FILE" ]]; then
                echo "No .credentials file found. Run 'socratic-cli user reset-password' to generate credentials." >&2
                exit 1
              fi

              if [[ -n "''${1:-}" ]]; then
                # Direct lookup by username
                MATCH=$(grep -E "^$1:" "$CREDS_FILE" || true)
                if [[ -z "$MATCH" ]]; then
                  echo "User '$1' not found in .credentials" >&2
                  exit 1
                fi
                PASSWORD=$(echo "$MATCH" | cut -d: -f2 | xargs)
                echo -n "$PASSWORD" | gpaste-client
                echo "Password for $1 copied to clipboard"
                exit 0
              fi

              # Interactive selection via fzf
              SELECTION=$(grep -E '^[^#].*:' "$CREDS_FILE" | fzf --prompt="Select user: " --height=10)
              if [[ -z "$SELECTION" ]]; then
                echo "No selection made"
                exit 0
              fi

              EMAIL=$(echo "$SELECTION" | cut -d: -f1 | xargs)
              PASSWORD=$(echo "$SELECTION" | cut -d: -f2 | xargs)

              echo -n "$PASSWORD" | gpaste-client
              echo "Password for $EMAIL copied to clipboard"
            '';
            help = "copy dev credentials to clipboard";
          }
        ];
      };
    };
}
