#!/bin/bash

# Activate virtual environment
source /Users/thorchristoffersen/visual/scripts/.venv/bin/activate

# Launch Streamlit app
streamlit run "$(dirname "$0")/web_app.py"
