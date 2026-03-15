#!/bin/bash

echo "🐝 Hive Trading System - Quick Start"
echo "===================================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10+"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+"
    exit 1
fi

if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL not found. Please install PostgreSQL 14+"
    exit 1
fi

if ! command -v redis-cli &> /dev/null; then
    echo "❌ Redis not found. Please install Redis 7+"
    exit 1
fi

echo "✅ All prerequisites found"
echo ""

# Setup database
echo "Setting up database..."
createdb hive_trading_system 2>/dev/null || echo "Database already exists"
psql hive_trading_system < backend/schema.sql
echo "✅ Database ready"
echo ""

# Setup backend
echo "Setting up backend..."
cd backend
pip install -r requirements.txt
cd ..
echo "✅ Backend dependencies installed"
echo ""

# Setup frontend
echo "Setting up frontend..."
cd frontend
npm install
cd ..
echo "✅ Frontend dependencies installed"
echo ""

# Check .env
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your API keys before running the system"
    exit 0
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the system:"
echo "  1. Terminal 1: cd backend && python main.py"
echo "  2. Terminal 2: cd backend && python api/main.py"
echo "  3. Terminal 3: cd frontend && npm run dev"
echo "  4. Open http://localhost:3000"
echo ""
echo "Optional: Start LM Studio on port 1234 for AI decisions"
