#!/bin/bash

# Run tests with coverage and generate HTML report
pytest --cov=. --cov-report=html --cov-report=term-missing

# Open the HTML report in the default browser (optional)
if [ -f "htmlcov/index.html" ]; then
    echo ""
    echo "Coverage report generated at: htmlcov/index.html"
    echo "Opening coverage report in browser..."
    open htmlcov/index.html 2>/dev/null || xdg-open htmlcov/index.html 2>/dev/null || echo "Please open htmlcov/index.html manually"
fi
