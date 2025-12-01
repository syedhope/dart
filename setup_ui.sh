#!/bin/bash
# ==============================================================================
# File Location: ./setup_ui.sh
# Description: 
#   Scaffolds the Frontend structure for Chainlit.
#   Separates UI components (Renderers, Bridge) from the main App loop.
# ==============================================================================

# 1. Public Assets (Images & CSS)
mkdir -p public/avatars
mkdir -p public/css

# 2. UI Source Code
mkdir -p src/ui

# 3. Create Files
# Main Entry Point
touch src/app.py

# UI Modules
touch src/ui/__init__.py
touch src/ui/setup.py      # Phase 1: Lobby, Sidebar, Avatars, Reset Logic
touch src/ui/bridge.py     # Phase 2: Async Logger (The Bridge)
touch src/ui/render.py     # Phase 2: Dataframes, Diffs, Steps
touch src/ui/actions.py    # Phase 3: HITL & Interactive Buttons

# Configuration
touch chainlit.md          # The "Welcome Screen" markdown
touch public/css/style.css # Cyberpunk Theme

echo "✅ UI Infrastructure Created."
echo "   - Entry Point: src/app.py"
echo "   - Modules:     src/ui/"
echo "   - Assets:      public/"