# ==============================================================================
# File Location: dart-agent/src/ui/render.py
# File Name: render.py
# Description:
# - Renders rich UI elements in Chainlit (dataframes, git diffs) for agent outputs.
# Inputs:
# - DataSnapshot and GitPR objects passed from mission flow.
# Outputs:
# - Chainlit messages with inline dataframe previews and markdown git diffs.
# ==============================================================================

import chainlit as cl
import pandas as pd
from src.utils.types import DataSnapshot, GitPR

async def render_data_snapshot(snapshot: DataSnapshot):
    """
    Renders a Pandas Dataframe to show "Before/After" proof.
    """
    if not snapshot or not snapshot.rows:
        return

    # Create Pandas DataFrame
    df = pd.DataFrame(snapshot.rows, columns=snapshot.columns)
    
    # Send as a native Chainlit Element
    await cl.Message(
        content=f"📊 **Data Snapshot: {snapshot.table_name}**",
        elements=[
            cl.Dataframe(
                name=f"{snapshot.table_name}_preview",
                data=df, 
                display="inline"
            )
        ]
    ).send()

async def render_git_diff(pr: GitPR):
    """
    Renders a Git Diff using Markdown syntax highlighting.
    """
    if not pr:
        return

    diff_text = f"""```diff
# Pull Request: {pr.title}
# Branch: {pr.branch_name}

{pr.diff_content}
```"""
    
    await cl.Message(
        content="**🐙 Generated Pull Request:**", 
        elements=[
            cl.Text(name="git_diff", content=diff_text, display="inline", language="diff")
        ]
    ).send()
