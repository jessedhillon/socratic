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
        overlays = [ inputs.devshell.overlays.default ];
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
          mkdir -p "$RABBITMQ_HOME" "$RABBITMQ_MNESIA_BASE" "$(dirname "$RABBITMQ_LOGS")"
        '';

        packages = with pkgs; [
          claude-code
          gh
          isort
          poetry
          postgresql_17
          pre-commit
          process-compose
          python313
          nodejs
          ruff
        ];

        commands = [
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
              set -euo pipefail
              SERVER_PIDS=()

              cleanup() {
                echo "Stopping API servers..."
                for pid in "''${SERVER_PIDS[@]}"; do
                  kill "$pid" 2>/dev/null || true
                done
              }
              trap cleanup EXIT


              echo "Starting Example API server..."
              poetry run python -m socratic.cli web serve example &
              SERVER_PIDS+=($!)

              sleep 3


              echo "Generating API client for Example..."
              pushd $PRJ_ROOT/socratic/web/example/frontend > /dev/null
              npx openapi-ts
              popd > /dev/null


              echo "API clients generated successfully"
            '';
            help = "generate TypeScript API clients from OpenAPI specs";
          }
          {
            name = "dev";
            command = "process-compose up";
            help = "start development services";
          }
        ];
      };
    };
}
