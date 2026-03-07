Research a dependency before adding it to the project.

The user will provide a package name, or you should use this skill proactively before running `yarn add`, `npm install`, or adding any new dependency.

## Process

1. **Check if it's already installed:**
```bash
grep "package-name" package.json
```

2. **Research the package:**
   - Search npm for the package: `npm view <package> description version license homepage`
   - Check bundle size: search bundlephobia.com or bundlejs.com
   - Check download stats and maintenance: last publish date, open issues, weekly downloads
   - Check if it's actively maintained (last commit, release frequency)

3. **Evaluate alternatives:**
   - Are there lighter alternatives?
   - Can this be done with existing dependencies already in the project?
   - Can this be done with a few lines of code instead of a dependency?
   - For React Native: does it require native linking? Does it support both iOS and Android?

4. **Check compatibility:**
   - Does it work with the project's current versions (React, React Native, Node)?
   - Any known issues with the current stack?
   - Does it have TypeScript types (built-in or `@types/`)?

5. **Present findings to the user:**
```
Package: <name>
Version: <latest>
Size: <minified + gzipped>
Last published: <date>
Weekly downloads: <count>
Licence: <licence>
Types: <built-in / @types / none>
Native linking: <yes/no> (React Native only)
Alternatives: <list>
Recommendation: <add / use alternative / write it yourself>
```

6. **Only proceed with installation after user approval.**

## Red flags (warn the user)
- Last published over 12 months ago
- Fewer than 1,000 weekly downloads
- No TypeScript support
- Licence incompatible with the project
- Large bundle size for what it does
- Requires native linking for a simple feature
- Many open issues with no maintainer responses
