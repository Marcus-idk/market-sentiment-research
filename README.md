# TradingBot

A lightweight US equities trading bot skeleton with strict data models, SQLite storage, and pluggable LLM providers (OpenAI, Gemini).

**📚 Please read all documentation in the `docs/` folder for a complete understanding of the project architecture, testing approach, and development roadmap.**

## Documentation Map

- **Summary**: Complete codebase index with all modules, functions, and database schema
  - [docs/Summary.md](docs/Summary.md)
  
- **Roadmap**: Development milestones (v0.1–v1.0), versioning scheme, and implementation status
  - [docs/Roadmap.md](docs/Roadmap.md)
  
- **Test Guide**: Where to write tests, naming conventions, and organizational patterns
  - [docs/Test_Guide.md](docs/Test_Guide.md)
  
- **Test Catalog**: Complete test inventory with file paths and test names
  - [docs/Test_Catalog.md](docs/Test_Catalog.md)
  
- **Writing Code**: Guidelines for code style, conventions, and best practices
  - [docs/Writing_Code.md](docs/Writing_Code.md)
  
- **Data API Reference**: External data sources (Finnhub, Polygon, SEC EDGAR, Reddit) with rate limits and coverage
  - [docs/Data_API_Reference.md](docs/Data_API_Reference.md)
  
- **LLM Providers Guide**: OpenAI and Gemini provider parameters, tools, and usage examples
  - [docs/LLM_Providers_Guide.md](docs/LLM_Providers_Guide.md)

## Prerequisites

- Python 3.13 or newer

## Development Setup

**1. Install runtime dependencies:**
```bash
pip install -r requirements.txt
```

**2. Install dev tools (formatters, linters, test runners):**
```bash
pip install -r requirements-dev.txt
```

**3. Activate pre-commit hooks (auto-format and lint before commits):**
```bash
pre-commit install
```

**4. (Optional) Install VS Code extensions:**
- VS Code will prompt: "This workspace has extension recommendations"
- Click "Install All" to install Ruff + Python extensions
- Or manually: Extensions (Ctrl+Shift+X) → Install recommendations from `.vscode/extensions.json`
- Format-on-save is already configured in `.vscode/settings.json`

## Code Quality

**Run Ruff (linter + formatter):**
```bash
# Lint with auto-fix
ruff check --fix .

# Format code
ruff format .
```

**Run Pylint (cyclic import detection):**
```bash
# Check for circular imports
pylint .
```

**Run jscpd (duplicate code detection):**
```bash
# Install (requires Node.js)
npm install -g jscpd

# Scan for duplicates
jscpd .
```

**Run Pyright (type checking):**
```bash
pyright
```

**Note**: Pre-commit hooks automatically run `ruff check --fix`, `ruff format`, `pyright`, and `pylint` before each commit. Run jscpd manually for periodic cleanup. Pylance provides real-time type checking in VS Code (basic mode).

## Testing

**Run all tests:**
```bash
pytest
```

**Run unit tests only (skip integration/network tests):**
```bash
pytest -m "not integration and not network"
```

**Coverage reports:**
- Coverage is automatically measured when running pytest
- Terminal shows missing lines for files under 100%
- Coverage must be ≥85% (configured in `.coveragerc`)
