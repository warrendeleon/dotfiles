# Third-party skills

The skills in this folder were copied from other people's repositories and then changed. Each folder holds the licence of its source in a `LICENSE` file. This page says where each skill came from and what was changed, as those licences require.

| Skill | Source | Commit | Licence |
|---|---|---|---|
| `better-layout`, `better-typography`, `better-colors` | [jakubkrehel/skills](https://github.com/jakubkrehel/skills), by Jakub Krehel | `a72290d` | MIT |
| `mobile-native`, `learn-taste`, `pick-ui-library` | [emilkowalski/skills](https://github.com/emilkowalski/skills), by Emil Kowalski | `0f2e23b` | MIT |
| `data-visualization`, `build-dashboard` | [anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins), by Anthropic | `e91a134` | Apache-2.0 |
| `design-taste-frontend` | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill), by Leonxlnx | `f6b7657` | MIT |
| `unslop` | [heydamir/unslop](https://github.com/heydamir/unslop), by heydamir | copied on 31 October 2026 | CC BY 4.0 |

## What was changed

Every file here may differ from its source. The changes, by skill:

- **All of them.** Author credits were removed from the skill text.
- **`learn-taste`.** Rewritten so that every rule is saved in a private wiki, scoped to one brand and one medium, and never in the project folder.
- **`learn-taste`, `pick-ui-library`.** The setting that stopped the model from loading them by itself was removed.
- **`mobile-native`, `pick-ui-library`.** The opening section that told the model how to greet the user was removed.
- **`data-visualization`.** The description was widened to cover a chart in any medium, with a note that the Python patterns apply to Python work only.
- **`build-dashboard`.** A line pointing at a file that is not part of this copy was removed.
- **`design-taste-frontend`.** The hook that ran at the end of every turn was removed, so its checker runs by hand. The scripts that start a local server were limited to the page's own folder, the headless browser was stopped from making background network calls, and file deletion was limited to the skill's own working folders. Web fonts loaded from Google were removed from one template.
- **`unslop`.** Author credits were removed. The licence asks for a link to it: <https://creativecommons.org/licenses/by/4.0/>.

## Photographs and icons

`design-taste-frontend/assets/photos/photos.json` lists every sample photograph with its photographer, its licence and its source page. The icon sets and their licences are listed in `design-taste-frontend/references/icons.md`.
