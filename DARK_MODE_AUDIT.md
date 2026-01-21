# Dark Mode Audit & Refinements

## Summary
Comprehensive dark mode optimization for all new UI elements added during the blog reader UX improvements.

## Changes Made

### 1. **ELO Badge (Top Priority)**
**Issue:** Bright gold gradient (`#FFD700` → `#FFA500`) was too intense in dark mode
**Solution:** Darker gold palette for better contrast
```css
/* Light mode */
background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);

/* Dark mode */
background: linear-gradient(135deg, #B8860B 0%, #CD853F 100%);
```
**Result:** Professional bronze-gold that maintains prestige while being easier on the eyes

---

### 2. **Enhanced Shadows**
**Issue:** Shadows using `rgba(0, 0, 0, 0.X)` were too subtle in dark mode
**Solution:** Increased shadow opacity for better depth perception

| Element | Light Mode | Dark Mode |
|---------|-----------|-----------|
| Cards (normal) | `0.06-0.08` | `0.3` |
| Cards (hover) | `0.12` | `0.4-0.5` |
| Hero section | `0.12` | `0.4` |

**Result:** Better visual hierarchy and card separation

---

### 3. **Card Borders**
**Issue:** Borders with `8%` opacity barely visible in dark mode
**Solution:** Increased border opacity to `15%`
```css
border-color: color-mix(in srgb, var(--md-default-fg-color) 15%, transparent);
```
**Affected elements:**
- Top post cards
- Post cards
- Navigation cards
- Featured posts
- Media gallery cards

---

### 4. **Text Shadows**
**Issue:** Hero title and stats had light shadows that didn't work in dark mode
**Solution:** Stronger shadows for text on gradient backgrounds
```css
.hero-title {
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5); /* was 0.2 */
}
```

---

### 5. **Tag Pills**
**Issue:** Pills with `10%` background too faint
**Solution:** Increased to `15%` for better visibility
```css
background: color-mix(in srgb, var(--md-primary-fg-color) 15%, transparent);
```
**Hover state:** Changed text color to dark (`#1a1a1a`) for better contrast

---

### 6. **Stat Badges**
**Issue:** Accent color badges on top posts had low contrast
**Solution:** Increased opacity from `15%` to `25%`

---

### 7. **Background Overlays**
**Issue:** Images in cards could reduce readability
**Solution:** Added subtle gradient overlay to post banners
```css
.post-banner::after {
  background: linear-gradient(to bottom, rgba(0,0,0,0) 0%, rgba(0,0,0,0.2) 100%);
}
```

---

### 8. **Related Posts Section**
**Issue:** Background too similar to page background
**Solution:** Added subtle white tint for section separation
```css
background: rgba(255, 255, 255, 0.03);
```

---

### 9. **Empty State**
**Issue:** Empty state message had no visual distinction
**Solution:** Added `5%` background tint for subtle highlighting

---

## Testing Checklist

### Elements Tested
- [x] ELO badges on top posts
- [x] Homepage hero gradient
- [x] Featured post card
- [x] Post grid cards
- [x] Navigation cards
- [x] Tag pills (all variants)
- [x] Related posts section
- [x] Media gallery cards
- [x] Stat badges
- [x] Text shadows on gradients

### Browsers/Devices
Test in:
- Chrome/Edge (light + dark)
- Firefox (light + dark)
- Safari (light + dark)
- Mobile viewport (both modes)

### Contrast Ratios
All text elements should meet WCAG AA standards:
- Normal text: 4.5:1 minimum
- Large text (18pt+): 3:1 minimum
- UI components: 3:1 minimum

**Key contrast improvements:**
- ELO badge: Dark gold on dark bg = higher contrast
- Tag pills: 15% opacity + primary color = readable
- Card borders: 15% opacity = visible separation

---

## Color Palette Reference

### Light Mode (Default)
- Primary: Teal (Material default)
- Accent: Amber (Material default)
- ELO Badge: `#FFD700` → `#FFA500` (bright gold)

### Dark Mode (Slate)
- Primary: Teal (adjusted by Material)
- Accent: Amber (adjusted by Material)
- ELO Badge: `#B8860B` → `#CD853F` (darker gold/bronze)

---

## Implementation Details

**File:** `src/egregora/rendering/templates/site/overrides/stylesheets/extra.css`
**Lines Added:** ~130 lines
**Selector:** `[data-md-color-scheme="slate"]`
**Scope:** All new UI elements from UX improvements

**Material Theme Integration:**
- Uses Material's color variables (`--md-*`)
- Respects user's system preference
- Works with manual theme toggle

---

## Future Enhancements

### Potential Additions
1. **High contrast mode** - For accessibility
2. **Custom color schemes** - Let users override gold badge color
3. **Auto dark mode** - Time-based switching
4. **Reduced motion** - Respect `prefers-reduced-motion`

### Monitoring
- Track user feedback on dark mode readability
- Test with various screen brightness levels
- Consider adding theme toggle directly in UI

---

## Notes

- All dark mode styles are scoped to `[data-md-color-scheme="slate"]`
- Changes are additive - light mode styles unchanged
- Material theme handles most color transitions
- Custom overrides only for new UI elements
- Shadow intensity critical for depth perception in dark mode
