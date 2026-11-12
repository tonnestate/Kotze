# KOTZE Harness papers (Word)

| File | Content |
| --- | --- |
| `KOTZE_Harness_Kaggle_Writeup.docx` | Submission writeup for the Gemma 4 Developer Agent Paper Track (body about 2,700 words plus citations) |
| `KOTZE_Harness_Full_Paper.docx` | Full manuscript with all state-machine tables, worked example and appendices |

All formulas are native Word equations (OMML), not images or code blocks, so they stay editable in Word. Figure 1 is embedded as an image.

## Rebuild

The Markdown sources and the figure are in `../source/`. Formulas are written as `$...$` and `$$...$$` LaTeX math, which pandoc converts to Word equations:

```bash
cd docs/papers/source
pandoc KOTZE_Harness_Kaggle_Writeup.md -f markdown+tex_math_dollars -o KOTZE_Harness_Kaggle_Writeup.docx
pandoc KOTZE_Harness_Full_Paper.md -f markdown+tex_math_dollars -o KOTZE_Harness_Full_Paper.docx
```

The committed `.docx` files were additionally built with a reference template (bordered tables, 9 pt table text) and pass an OOXML schema check.
