# Frontend Security Notes

## XSS and Rich Text Editors

Rich text editors that produce HTML are a classic XSS (Cross-Site Scripting) attack vector.
If HTML produced by the editor is stored and later rendered with `dangerouslySetInnerHTML`,
an attacker could inject `<script>` tags or other malicious payloads.

### How Tiptap mitigates this

Tiptap uses ProseMirror's schema system — a whitelist model. Only node types explicitly
defined in your schema (heading, bullet, paragraph, etc.) are allowed in the document.
Script tags, iframes, and arbitrary HTML are blocked at the editor level by default.
This makes Tiptap safer than a raw `contentEditable + innerHTML` implementation.

### The rule that always applies

**Always sanitize HTML on the server before storing it.** Never trust client output.
The editor's whitelist is a UX-level defense, not a security guarantee — a determined
attacker can bypass the client. The server is the last line of defense.

When Sundial moves to a real backend:
- Strip or escape any HTML before writing to the database
- Use a server-side sanitization library (e.g. `bleach` in Python, `DOMPurify` server-side in Node)
- Define an explicit allowlist of tags and attributes that match what Tiptap produces
- Never pass raw editor HTML to `eval()`, a template engine, or any server-side renderer

---

## Pinned Dependency Versions

### Why we pin

`^` in package.json (e.g. `"tailwindcss": "^3.4.19"`) means "automatically accept any
minor or patch update." This is convenient but introduces two risks:

1. **Breaking changes** — a minor update can change behavior in ways that break the UI
2. **Supply chain attacks** — a compromised package version could ship malicious code;
   auto-upgrading pulls it in automatically

Pinning to an exact version means you consciously decide when to upgrade and can review
the changelog before doing so.

### Pinned versions in this project

| Package | Pinned version | Reason |
|---------|---------------|--------|
| `tiptap` (when added) | pin to install version | Rich text editor — upgrades can change editor behavior, serialization format, or keybindings in subtle ways that corrupt stored content |
| `tailwindcss` | `3.4.19` | We explicitly downgraded from v4 to v3 for compatibility. Auto-upgrade would pull in v4 and break the entire CSS layer silently |
| `react` / `react-dom` | pin when stable | Major React versions can break hooks behavior |

### How to pin in package.json

Remove the `^` prefix:

```json
// Unpinned (auto-upgrades on npm install)
"tailwindcss": "^3.4.19"

// Pinned (exact version, always)
"tailwindcss": "3.4.19"
```

### Upgrade process when pinned

1. Check the package's changelog / release notes
2. Read for breaking changes or security fixes
3. Update the version number in package.json manually
4. Run `npm install`
5. Test the affected areas of the UI
6. Commit the package.json and package-lock.json together

### npm audit

Run `npm audit` regularly. It scans the entire dependency tree (including transitive
dependencies — dependencies of your dependencies) for known CVEs (published security
vulnerabilities). Fix high/critical findings before shipping.

```bash
npm audit
npm audit fix   # auto-fixes where safe
```

---

## Supply Chain Risk

Any npm package is a dependency you're trusting. A compromised package can ship
malicious code that runs in your app or your build pipeline.

**Mitigations in use:**
- Pin versions (see above) — don't auto-pull new releases
- Use well-maintained packages with many contributors and public audit history
- Commit `package-lock.json` — ensures every developer and CI run installs the
  exact same dependency tree, no surprises
- Run `npm audit` in CI so vulnerable dependencies block deploys

**Packages chosen for this project and why they're considered safe:**
- `tiptap` — 400+ contributors, built on ProseMirror (10+ years, maintained by Marijn Haverbeke, author of Eloquent JavaScript)
- `tailwindcss` — maintained by Tailwind Labs, millions of users, publicly audited
- `lucide-react` — MIT, widely used icon set, no network calls
- `react-router-dom` — maintained by Remix/Shopify team, industry standard
