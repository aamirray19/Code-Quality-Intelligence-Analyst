## Goal

Repurpose the landing page for your **Code Quality Intelligence Agent** project. Replace the prompt analyzer with a GitHub URL + ZIP upload input, remove the Pricing section and everything below it. UI only — backend wiring (FastAPI) comes later.

## Changes

### 1. Hero (`src/components/HeroSection.tsx`)
- Badge: "Now analyzing public repos" (replaces cohort copy).
- Headline: **"Ship cleaner code with your"** / **"Code Quality Intelligence Agent."** (keeps the two-line constraint, primary-orange + Lora accent on "Code Quality Intelligence").
- Subheadline: "Point it at any repository — get a deep report on bugs, smells, security, and complexity in seconds."
- Remove `CountdownTimer` and `EnrollButton` from hero.
- Replace `<PromptLab />` with a new `<RepoAnalyzer />` component.

### 2. New `src/components/RepoAnalyzer.tsx` (replaces PromptLab)
A single unified input card matching the existing PromptLab aesthetic (rounded, translucent bg, primary glow on focus):
- **Tab toggle**: `GitHub URL` | `Upload ZIP` (same sliding-pill style as the pricing PaymentToggle, reused visually).
- **GitHub mode**: text input with `https://github.com/...` placeholder + GitHub icon, "Analyze" button on the right.
- **ZIP mode**: drag-and-drop dropzone with cloud-upload icon, "Drop a .zip or click to browse", accepts `.zip` only, shows selected filename + size, "Analyze" button below.
- Client-side validation only (zod): valid GitHub URL pattern; ZIP MIME type + size cap (e.g. 50 MB).
- On submit: show a toast "Analysis queued — backend coming soon" and a disabled "Analyzing…" state for ~1.5s. No network call. Leave a clearly marked `// TODO: POST to FastAPI` hook so wiring later is trivial.

### 3. Page composition (`src/pages/Index.tsx`)
Trim to just:
```
Navbar
HeroSection (with RepoAnalyzer)
Footer
```
Remove: `CourseStructureSection`, `ReviewsSection`, `PricingSection`, `WhyUsSection`, `FAQsSection`, `FinalCTASection`. Files stay on disk (easy to restore) but are no longer imported.

### 4. Navbar (`src/components/Navbar.tsx`) + `src/config/navigation.ts`
- Clear `navLinks` (curriculum/reviews/pricing/why-us/faqs all point to removed sections).
- Keep only `Contact` in footer extras, or remove nav links entirely and leave just the logo + a single "Analyze" CTA that scrolls to the analyzer.

### 5. Branding touch-ups
- `Logo` wordmark: change "PromptMaster" → "CodeIQ" (short, fits the existing `> |` cursor mark). Keep orange brand color.
- `index.html` `<title>` + meta description updated to "Code Quality Intelligence Agent".
- Footer tagline updated; remove Explore links that pointed to deleted sections.

### 6. Cleanup
- Don't delete the unused section components yet — just stop importing them. Keeps the diff reviewable and lets you restore copy if needed.
- Leave Contact page and its Supabase edge function untouched (still works as a generic contact form).

## Technical notes

- `RepoAnalyzer` uses `react-dropzone`-style native handling via `<input type="file" accept=".zip" />` + a styled label — no new dependency needed.
- Zod schema:
  ```ts
  const githubUrl = z.string().trim().url().regex(/^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/, "Enter a valid GitHub repo URL");
  const zipFile = z.instanceof(File).refine(f => f.name.endsWith(".zip"), "Must be a .zip").refine(f => f.size < 50 * 1024 * 1024, "Max 50 MB");
  ```
- Backend hook stub: `async function analyze(payload: { kind: "github"; url: string } | { kind: "zip"; file: File })` with a `// TODO` comment pointing at your FastAPI endpoint.

## Out of scope (for later)

- Real FastAPI integration, results/report page, auth, persistence.
