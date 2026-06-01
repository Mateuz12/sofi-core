import xlrd

FILE = r"C:\Users\luma.dias\Documents\PROJETO\AUTOMAÇÃO DEPÓSITOS\RELATORIO_CALAMO_xml\modelos_xmls\MODELO BH.xls"

wb = xlrd.open_workbook(FILE, formatting_info=True)

def col_label(c):
    """Convert column index to letter(s), e.g. 0->A, 23->X."""
    if c < 26:
        return chr(ord('A') + c)
    return chr(ord('A') + (c // 26) - 1) + chr(ord('A') + (c % 26))

print("=" * 80)
print("SHEET NAMES:", wb.sheet_names())
print("=" * 80)

# ---------------------------------------------------------------
# 1) Notas Fiscais – rows 1..15, cols 0..9 (A-J)
# ---------------------------------------------------------------
print("\n")
print("=" * 80)
print("1. NOTAS FISCAIS SHEET - ROWS 1-15, COLS A-J (0-9)")
print("=" * 80)

sh_nf = wb.sheet_by_name("Notas Fiscais")
print(f"  Actual dimensions: rows={sh_nf.nrows}, cols={sh_nf.ncols}\n")

for r in range(1, min(16, sh_nf.nrows)):
    print(f"--- Row {r} ---")
    for c in range(min(10, sh_nf.ncols)):
        cell = sh_nf.cell(r, c)
        print(f"  {col_label(c)}{c}: value={repr(cell.value)}, type={cell.ctype}")

# ---------------------------------------------------------------
# 2) Notas Fiscais – XF index + background colour per cell
# ---------------------------------------------------------------
print("\n")
print("=" * 80)
print("2. NOTAS FISCAIS - CELL XF INDEX & BACKGROUND COLOUR (rows 1-15, cols 0-9)")
print("=" * 80)

for r in range(1, min(16, sh_nf.nrows)):
    print(f"\n--- Row {r} ---")
    for c in range(min(10, sh_nf.ncols)):
        cell = sh_nf.cell(r, c)
        xf_index = sh_nf.cell_xf_index(r, c)
        xf = wb.xf_list[xf_index]
        bg = xf.background
        print(f"  Col{c}: val={repr(cell.value)} | xf_idx={xf_index} "
              f"| format_key={xf.format_key} | font_index={xf.font_index} "
              f"| fill_pattern={bg.fill_pattern} "
              f"| pattern_colour_index={bg.pattern_colour_index} "
              f"| background_colour_index={bg.background_colour_index}")

# ---------------------------------------------------------------
# 3) Base sheet – rows 1..5, cols A..X (0-23)
# ---------------------------------------------------------------
print("\n")
print("=" * 80)
print("3. BASE SHEET - ROWS 1-5, COLS A-X (0-23)")
print("=" * 80)

sh_base = wb.sheet_by_name("Base")
print(f"  Actual dimensions: rows={sh_base.nrows}, cols={sh_base.ncols}\n")

for r in range(1, min(6, sh_base.nrows)):
    print(f"--- Row {r} ---")
    for c in range(min(24, sh_base.ncols)):
        cell = sh_base.cell(r, c)
        print(f"  {col_label(c)}{c}: {repr(cell.value)} (type={cell.ctype})")

# ---------------------------------------------------------------
# 4) Merged cells – Notas Fiscais
# ---------------------------------------------------------------
print("\n")
print("=" * 80)
print("4. MERGED CELLS - NOTAS FISCAIS")
print("=" * 80)

if hasattr(sh_nf, 'merged_cells') and sh_nf.merged_cells:
    for mc in sh_nf.merged_cells:
        # each is (rlo, rhi, clo, chi) - Excel style, hi is exclusive
        print(f"  rows {mc[0]}-{mc[1]-1}, cols {mc[2]}-{mc[3]-1}  "
              f"-> top-left value: {repr(sh_nf.cell_value(mc[0], mc[2]))}")
else:
    print("  No merged cells found")

# ---------------------------------------------------------------
# 5) Check background colours on rows 4-10 of Notas Fiscais
# ---------------------------------------------------------------
print("\n")
print("=" * 80)
print("5. NOTAS FISCAIS - BACKGROUND / PATTERN COLOURS ON ROWS 4-10")
print("=" * 80)

print("Legend:")
print("  fill_pattern: 0=none, 1=solid, 2=gray50, 3=gray75, 4=gray25, ...")
print("  pattern_colour_index: foreground colour (0=default, 64=automatic)")
print("  background_colour_index: background colour")
print()

found_any_color = False
for r in range(4, min(11, sh_nf.nrows)):
    print(f"--- Row {r} ---")
    for c in range(sh_nf.ncols):
        xf_index = sh_nf.cell_xf_index(r, c)
        xf = wb.xf_list[xf_index]
        bg = xf.background
        has_fill = bg.fill_pattern != 0
        has_fg = bg.pattern_colour_index not in (0, 64, 65, None)
        has_bg = bg.background_colour_index not in (0, 64, 65, None)
        if has_fill or has_fg or has_bg:
            found_any_color = True
            print(f"  Col{c}: xf_idx={xf_index} | "
                  f"fill_pattern={bg.fill_pattern} | "
                  f"pattern_colour_index={bg.pattern_colour_index} | "
                  f"background_colour_index={bg.background_colour_index} | "
                  f"val={repr(sh_nf.cell_value(r, c))}")
        else:
            print(f"  Col{c}: (no colour) val={repr(sh_nf.cell_value(r, c))}")

if not found_any_color:
    print("  (no cells with non-default background colours found in rows 4-10)")

# ---------------------------------------------------------------
# Bonus: colour map
# ---------------------------------------------------------------
print("\n")
print("=" * 80)
print("BONUS: COLOUR MAP (all entries)")
print("=" * 80)
try:
    cmap = wb.colour_map
    if cmap:
        for idx in range(len(cmap)):
            if cmap[idx] is not None:
                print(f"  colour_index {idx}: {cmap[idx]}")
    else:
        print("  colour_map is empty / None")
except AttributeError:
    print("  colour_map not available")

print("\nDone.")
