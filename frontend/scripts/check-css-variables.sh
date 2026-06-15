#!/bin/bash
# Check for problematic CSS variable patterns in UI components
# These patterns don't resolve correctly in portals (dialogs, dropdowns, popovers)

echo "Checking for problematic CSS variables in UI components..."

PATTERNS=(
  "text-foreground"
  "text-popover-foreground"
  "text-accent-foreground"
  "text-muted-foreground"
  "text-primary-foreground"
  "text-secondary-foreground"
  "text-card-foreground"
  "bg-popover"
  "bg-accent"
  "bg-muted"
  "bg-card"
  "bg-background"
  "ring-offset-background"
)

FOUND=0

for pattern in "${PATTERNS[@]}"; do
  results=$(grep -r "$pattern" src/components/ui/ --include="*.tsx" 2>/dev/null)
  if [ -n "$results" ]; then
    echo ""
    echo "Found '$pattern':"
    echo "$results"
    FOUND=1
  fi
done

if [ $FOUND -eq 0 ]; then
  echo "No problematic CSS variables found."
  exit 0
else
  echo ""
  echo "ERROR: Found problematic CSS variables that may not resolve in portals."
  echo "Replace with explicit Tailwind colors (e.g., text-gray-700, bg-white)."
  echo "See frontend/AGENTS.md for guidelines."
  exit 1
fi
