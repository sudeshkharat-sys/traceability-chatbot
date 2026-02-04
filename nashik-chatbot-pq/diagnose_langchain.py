
import os

file_path = r"C:\Users\50014665\ai\Lib\site-packages\langchain_community\vectorstores\opensearch_vector_search.py"

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    exit(1)

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start = max(0, 1360)
end = min(len(lines), 1380)

print(f"--- Content of {file_path} (lines {start+1} to {end}) ---")
for i in range(start, end):
    print(f"{i+1}: {repr(lines[i])}")
