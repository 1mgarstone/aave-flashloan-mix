#!/bin/bash

# Update port number from 5000 to 3146 across the project
echo "🔄 Changing port numbers from 5000 to 3146..."

# Find and replace in Python files
find . -type f -name "*.py" -exec sed -i 's/5000/3146/g' {} +

# Find and replace in other relevant files (if necessary, adjust as needed)
find . -type f -name "*.html" -exec sed -i 's/5000/3146/g' {} +
find . -type f -name ".replit" -exec sed -i 's/5000/3146/g' {} +

echo "✅ Port numbers updated to 3146!"