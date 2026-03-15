#!/bin/bash

echo "🧪 Running Hive Trading System Tests"
echo "====================================="
echo ""

# Check if pytest is installed
if ! python3 -m pytest --version &> /dev/null; then
    echo "Installing test dependencies..."
    pip install -r tests/requirements.txt
fi

# Check if Redis is running
if ! redis-cli ping &> /dev/null; then
    echo "⚠️  Warning: Redis is not running. Some tests may fail."
    echo "   Start Redis with: redis-server"
    echo ""
fi

# Check if PostgreSQL is running
if ! pg_isready &> /dev/null; then
    echo "⚠️  Warning: PostgreSQL is not running. Some tests may fail."
    echo "   Start PostgreSQL or check connection settings."
    echo ""
fi

# Run tests
echo "Running tests..."
echo ""

python3 -m pytest tests/ -v --tb=short

echo ""
echo "Test run complete!"
