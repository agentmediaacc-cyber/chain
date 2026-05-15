import os
import re

def audit_templates(directory):
    errors = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                with open(path, 'r') as f:
                    content = f.read()
                    
                    # Check for duplicate blocks in same file
                    blocks = re.findall(r'{%\s*block\s+(\w+)\s*%}', content)
                    if len(blocks) != len(set(blocks)):
                        dupes = [b for b in set(blocks) if blocks.count(b) > 1]
                        errors.append(f"Duplicate blocks {dupes} in {path}")
                        
                    # Check for unclosed blocks
                    opens = len(re.findall(r'{%\s*block', content))
                    closes = len(re.findall(r'{%\s*endblock', content))
                    if opens != closes:
                        errors.append(f"Mismatched blocks ({opens} open, {closes} close) in {path}")
                        
                    # Check for broken extends (simple check)
                    if '{% extends' in content and not re.search(r'{%\s*extends\s+["\'][\w/.-]+["\']\s*%}', content):
                        errors.append(f"Potentially broken extends in {path}")

    return errors

if __name__ == "__main__":
    results = audit_templates('templates')
    if not results:
        print("No template errors found.")
    for err in results:
        print(err)
