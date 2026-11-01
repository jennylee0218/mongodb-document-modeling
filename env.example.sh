# copy to env.sh (git-ignored and denied to Claude). Atlas → Connect → Drivers → copy the mongodb+srv string.
export MDB_URI='mongodb+srv://<your-user>:<password>@<cluster>.mongodb.net/'            # you: runs inclass.py, creates the indexes
export MDB_MCP_CONNECTION_STRING='mongodb+srv://claude_ro:<password>@<cluster>.mongodb.net/'  # Claude: role 'read' on sample_mflix only
