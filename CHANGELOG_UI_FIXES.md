# UI Fixes - Table Flashing and Tooltip Improvements

## Issues Fixed

### 1. Table Flashing When Moving Castles
**Problem**: When moving a castle on the grid, the castle table would flash distractingly.

**Root Cause**: The table row hover events (`mouseenter` and `mouseleave`) were calling `drawMap(mapData)`, which redraws the entire canvas. This caused unnecessary re-renders when hovering over table rows.

**Solution**: Removed `drawMap(mapData)` calls from table row hover event listeners (lines 673, 678 in app.js).

**Files Changed**: `static/app.js`

---

### 2. Tooltip Timing and Placement
**Problem**: 
- Tooltips were showing immediately on both the table and the grid
- No delay meant accidental hover would trigger tooltips

**Root Cause**: The `showCastleTooltip()` function was being called immediately on any hover event without delay.

**Solution**: 
- Added a 1500ms (1.5 second) delay timer for tooltips on the grid/canvas
- Kept instant tooltips on table rows (this is user-friendly for table interaction)
- Clear timer when:
  - Mouse leaves canvas
  - User starts panning
  - User starts dragging entities
  - User hovers over a different castle

**Implementation Details**:
- Added `tooltipTimer` variable to track the setTimeout
- Added `TOOLTIP_DELAY_MS` constant (1500ms)
- Modified `onMouseMovePan()` function to implement delayed tooltip logic
- Modified canvas `mouseleave` event to clear timer

**Files Changed**: `static/app.js`

---

## Testing Instructions

### Test 1: Table Flashing
1. Open the application
2. Hover over different table rows
3. Move a castle on the grid
4. **Expected**: No flashing or flickering in the table

### Test 2: Tooltip on Grid
1. Move mouse over a castle on the grid/canvas
2. **Expected**: Tooltip appears after 1.5 seconds of hovering
3. Move mouse away before 1.5 seconds
4. **Expected**: No tooltip appears

### Test 3: Tooltip on Table
1. Hover over a table row
2. **Expected**: Tooltip appears immediately (no delay)

### Test 4: Tooltip Cancellation
1. Start hovering over a castle on grid
2. Before 1.5 seconds, start panning or dragging
3. **Expected**: Tooltip does not appear

---

## Code Changes Summary

### Variables Added
```javascript
let tooltipTimer = null;  // Timer for delayed tooltip display
const TOOLTIP_DELAY_MS = 1500;  // 1.5 seconds delay for canvas tooltips
```

### Functions Modified
1. `renderCastleTable()` - Removed `drawMap()` calls from table row hover events
2. `onMouseMovePan()` - Added tooltip delay logic for canvas hover
3. Canvas `mouseleave` event - Added timer cleanup

---

## Performance Impact
- **Positive**: Reduced unnecessary `drawMap()` calls = better performance
- **Neutral**: Added setTimeout timers are lightweight and properly cleaned up

---

## Browser Compatibility
All changes use standard JavaScript features:
- `setTimeout()` / `clearTimeout()` - Supported in all browsers
- Event listeners - Standard DOM API

No special polyfills or libraries required.
