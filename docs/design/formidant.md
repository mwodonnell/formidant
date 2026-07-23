# formidant — design & plan

**Status:** design pass in progress, started 2026-07-22 with mjo. **Phase 1 — Acceptance
criteria: CLOSED 2026-07-22 — all criteria (B1–B5, L1–L6, R1–R6, P1–P4, X1–X3, D1–D4), the
worked example, and the three-piece architecture accepted by mjo. Phase 2 — Test design: in
progress. No code exists.** Pass order for this project (mjo, 2026-07-22): acceptance
criteria → test design → build design (decisions/artifacts/tickets).
This doc pioneers the acceptance-criteria and test-design sections; once proved out here they
get backported to `~/.claude/design-doc-reference.md` (agreed 2026-07-22 — prove out first,
then amend the standard). This repo is standalone; the README will grow into the canonical
record if the project sprouts subsystems.

## Implementation status (updated 2026-07-22)

Nothing built. Design phase 1 (acceptance criteria) drafted and awaiting review.

## Context

**formidant is a Pydantic-based web form system: binding + validation + bound-form lifecycle +
server-side HTML rendering.** It exists because the quadrant is empty: nobody ships pydantic
validation with a server-side renderer and a bound re-render story (ecosystem survey,
2026-07-22 — see Key references). Django Forms owns that lifecycle but with a widget/Form API
mjo actively wants to leave; django-ninja proves the clean pydantic binding pattern
(parse → flat dict → inflate → `model_validate`) but is API-only, has no renderer, and its
binding is baked into the framework.

Shape of the build (from the 2026-07-22 research pass, to be confirmed as Decisions in phase 3):

- **Django-first, framework-agnostic core.** The core binds from a small multidict protocol,
  never a Django request; a thin Django adapter feeds it. Flask/Litestar adapters are possible
  later but not designed for now beyond keeping the seam clean.
  **Review addition (mjo, 2026-07-22):** adapter authoring must be a *public, documented
  surface* so third parties can build adapters out-of-tree — formidant must never be passed
  up because integration is hard (→ P4). The DX north star is django-ninja's multi-source
  signature binding (path + query + `Form[Item]` co-declared in one view signature),
  approached "as close as we possibly can" per adapter (→ D4).
- **Three pieces:** (1) binding core — django-ninja's flatten/inflate + error shaping as the
  starting point (MIT), extended with bracket-notation nesting; (2) bound-form wrapper — the
  raw-data + per-field-errors + re-render object (no good prior art; the core design problem);
  (3) renderer — type→widget mapping via `Annotated` metadata, template-based, htmx-friendly.

**Rejected framings** (mjo, 2026-07-22):

- *JSON-Schema → client-side renderer (RJSF path)* — mature but requires a React pipeline and
  duplicates validation client-side; the whole point is server-side rendering for htmx/SSR apps.
- *Django-Forms feature parity* — formsets, ModelForm/ORM introspection, widget media, i18n are
  a drowning-depth long tail. formidant targets hand-defined schemas; list-of-nested-model
  editing over htmx replaces formsets; ModelForm is explicitly out of scope.
- *Framework-agnostic-first* — designing Flask/Litestar adapters on day one is speculative
  flexibility. The protocol seam keeps the door open at near-zero cost; that is enough.

## Acceptance criteria — ACCEPTED (mjo, 2026-07-22) except items marked DRAFT

What "done and correct" means for v1. Each criterion is stated so a test or demo step can be
pointed at it; the Test design section (phase 2) maps test cases to these IDs. Grouped:
**B** binding, **L** lifecycle, **R** rendering, **P** portability, **X** security/correctness,
**D** developer experience. Non-goals are listed after the criteria and are as binding as the
criteria themselves.

### B — Binding & validation

- **B1 — Vanilla pydantic models bind.** Any plain `pydantic.BaseModel` (v2) binds from
  form-encoded data to a validated instance with stock pydantic coercion, constraints, and
  defaults. No formidant base class, mixin, or model_config required.
- **B2 — Bracket-notation nesting.** `address[city]` binds to nested models and
  `items[0][name]` binds to `list[Model]` fields — a strict superset of django-ninja, which
  supports neither (leaf-name nesting only, no lists of nested objects).
- **B3 — Scalar lists via repeated keys.** `tags=a&tags=b` binds to `list[str]` (multi-select /
  checkbox-group encoding).
- **B4 — HTML form quirks are normalized by default.** Unchecked checkbox (absent key) → False
  or field default for `bool` fields; empty string → `None`/default for Optional and
  non-string fields. No user-defined annotated types needed (django-ninja punts this to a
  documented user recipe; formidant does not).
- **B5 — File uploads bind** to a declared file field type through the same pipeline.

### L — Bound-form lifecycle

- **L1 — One bind call, two inspectable outcomes.** Binding submitted data yields a bound form
  object: on valid input it exposes the typed pydantic instance; on invalid input it exposes
  per-field errors (keyed by field path, mapped from pydantic `loc`) and the raw submitted
  values. No exception-catching in user view code.
- **L2 — Raw input survives re-render.** An invalid bound form re-renders with the user's raw
  input preserved verbatim — including values that failed coercion (e.g. `"abc"` typed into an
  int field re-renders as `"abc"`, not blank, not `0`).
- **L3 — Errors render in place.** Field errors render adjacent to their field; model-level
  errors (`model_validator`) render at form level. Nested/list field errors attach to the
  specific nested input they belong to.
- **L4 — Unbound render with initial values.** A form renders unbound from the model class
  alone (defaults populate inputs) and from an existing model instance (edit-form case).
- **L5 — ACCEPTED (mjo, 2026-07-22) — Valid-only view style.** Views can opt
  into receiving only valid, typed form instances: the adapter intercepts GET (unbound render)
  and invalid POST (re-render with errors) so the view body never contains an
  `if form.is_valid` branch. Response policy on invalid input belongs to the **adapter**, not
  the core: the Django HTML adapter re-renders the template with the bound form; an API-style
  adapter is free to raise/return its framework's 4xx instead (django-ninja returns 422). The
  core stays exception-free and only ever reports the L1 outcome. The low-level bind-and-branch
  API (L1) remains available as the escape hatch. Prior art: django-ninja/FastAPI
  (validate-before-handler), Django's own `FormView.form_valid()` hook (branch-free user code
  via inversion of control).
- **L6 — ACCEPTED (mjo, 2026-07-22) — Escape hatches around the automatic
  invalid response.** Two mechanisms, solving two different cases:
  1. **`on_invalid` hook** — a callback (per-view, with an adapter-level default) invoked
     between validation failure and the automatic response; it may return its own response or
     defer to the default. Covers logging/metrics/alternate responses without hacking into
     the request cycle.
  2. **Annotation-declared contract** — `form: SignupForm` means valid-only (short-circuit on
     invalid, the L5 default); `form: Bound[SignupForm]` means the body always runs and
     receives the L1 bound-form object, invalid included, restoring manual branching with
     decorator ergonomics. What enters the view is exactly what the signature declares.

### R — Rendering

- **R1 — Full default widget matrix.** Every v1-supported field type renders a sensible
  default widget with zero configuration. v1 matrix: `str`→text, `bool`→checkbox,
  `int`/`float`/`Decimal`→number, `date`/`datetime`/`time`→native date/datetime-local/time
  inputs, `EmailStr`→email, `SecretStr`→password, `HttpUrl`→url, `UUID`→text,
  `StrEnum`/`Literal`→select, `Optional[T]`→T's widget non-required, `list[scalar]`→
  checkbox group or multi-select, nested `BaseModel`→fieldset, `list[BaseModel]`→repeatable
  group with add/remove, file field→file input. Constraints flow to attributes:
  `max_length`→`maxlength`, `ge`/`le`→`min`/`max`, required→`required`.
- **R2 — Presentation via `Annotated`, orthogonal to validation.** Widget choice, label, help
  text, placeholder, and arbitrary HTML attrs are overridable per field through `Annotated`
  metadata that has zero effect on the model's validation or serialization behavior.
- **R3 — Template-overridable output.** Default rendering ships as templates users can
  override at the form, fieldset, and widget level (the crispy-forms seam, not Python
  string-building the user can't touch). **Review note (mjo, 2026-07-22):** default templates
  are deliberately minimal — extremely simple, clean markup; Django's default rendering does
  too much and is the anti-pattern here.
- **R4 — htmx-friendly partials.** A single field (widget + errors) can be rendered in
  isolation, so hx-swap of one field or one list row works without re-rendering the form.
- **R5 — Round-trip fidelity.** For any v1-matrix model instance: render → submit the rendered
  inputs' values unchanged → binds valid and equals the original instance.
- **R6 — ACCEPTED (mjo, 2026-07-22) — Render parity between core and adapter
  sugar.** Rendering lives in the framework-free core (`form.render()`,
  `render_field(form, "email")` — names illustrative); `{% formidant %}` /
  `{% formidant_field %}` are thin Django template tags delegating to it. Byte-identical
  output, proven by a test comparing tag output to core output. Engine: Jinja2 behind a
  narrow seam — see Decisions.

### P — Portability

- **P1 — Core imports no Django.** `import formidant.core` (binding, lifecycle, widget
  resolution) succeeds and pulls in no `django.*` module. Enforced by a test, not convention.
- **P2 — All request access goes through one protocol.** The core consumes a defined
  `FormData` protocol (multidict with `getlist` + files mapping); the Django adapter is the
  only place `request.POST`/`request.FILES` appear.
- **P3 — The Django adapter is thin.** Adapter + CSRF/template integration ≤ ~150 lines of
  non-test code. If it trends past that, the seam is wrong — stop and redesign.
- **P4 — ACCEPTED (mjo, 2026-07-22) — Adapters are buildable out-of-tree.** The
  adapter-authoring surface (the `FormData` protocol, signature-introspection entry points,
  and error-shape contract) is public and documented; a third-party adapter imports nothing
  underscore-prefixed. Measured by: our own Django adapter uses only that public surface.

### X — Security & correctness

- **X1 — No XSS through re-render.** Raw user input containing HTML/script is escaped in all
  re-render paths (values, error messages, attrs). Proven by test with hostile input.
- **X2 — CSRF present by default in Django.** The Django-adapter form rendering includes the
  CSRF token without the user asking; the core exposes a slot mechanism so other adapters can
  do the same.
- **X3 — Out-of-schema keys are ignored, never bound.** Extra POST keys cannot inject fields
  (mass-assignment posture; pydantic `extra="forbid"` models surface it as a form error, not a
  500).

### D — Developer experience (the "is it actually nicer than Django Forms" measures)

- **D1 — The canonical example fits on a screen.** A signup form (email, password, display
  name, TOS checkbox) — schema + view with validate/re-render/redirect + template include —
  in ≤ 25 lines of user-written Python and ≤ 5 lines of template, imports excluded.
- **D2 — One schema, three consumers.** The same pydantic model works unmodified as: a
  formidant form, a django-ninja request body, and a plain serialization schema. No dual
  definitions (the Personalkollen drift problem is the failure mode this kills).
- **D3 — Errors are human-readable by default.** Default pydantic v2 messages render as-is and
  are acceptable; a per-field override hook exists for custom wording. (Full i18n: deferred.)
- **D4 — ACCEPTED (mjo, 2026-07-22) — Ninja-style multi-source binding in the
  Django adapter.** A decorated plain Django view can co-declare path, query, and form
  parameters in one signature (`def update(request, item_id: int, q: str, item: Form[Item])`)
  and each is bound from its source — the django-ninja DX on vanilla Django views. This rides
  the same introspection core we port anyway; it is the flagship demo of P4's adapter surface.

### Non-goals for v1 (binding)

- **No ModelForm equivalent** — no ORM introspection, no `save()`.
- **No formsets** — `list[BaseModel]` + htmx row add/remove is the replacement.
- **No client-side validation or JS shipped** — htmx attributes in templates at most.
- **No i18n of messages** — deferred round.
- **No async binding path** — deferred until an async adapter exists to need it.

## Worked example — ACCEPTED with the three-piece architecture (mjo, 2026-07-22)

Illustrative only: API names are OPEN until phase 3; the *shape* is what's being approved.

**In plain terms:** you write one plain pydantic model. Piece 1 turns a browser's
form-encoded POST into that model via pydantic validation. Piece 2 wraps the outcome in a
bound-form object (or keeps invalid submissions out of your view entirely). Piece 3 renders
the model class — or a failed submission with its errors — as minimal HTML from overridable
templates. The same model works unmodified in django-ninja or anywhere else pydantic goes.

### The schema — plain pydantic, presentation via `Annotated` (input to all three pieces)

```python
class SignupForm(BaseModel):
    email: EmailStr
    display_name: Annotated[str, Meta(label="Display name", placeholder="How you'll appear")]
    password: SecretStr
    accept_tos: Annotated[bool, Meta(label="I accept the terms of service")]

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
        return v
```

`Meta` is presentation-only metadata: pydantic ignores it, so validation/serialization are
untouched (R2) and the model stays usable as a ninja body (D2).

### Piece 1 — binding core (framework-free)

What the wire carries vs. what pydantic sees, for a nested example:

```
POST name=Ada&address[city]=Oslo&items[0][sku]=A1&items[0][qty]=2&tags=red&tags=blue

→ inflate →  {"name": "Ada", "address": {"city": "Oslo"},
              "items": [{"sku": "A1", "qty": "2"}], "tags": ["red", "blue"]}

→ Order.model_validate(...)   # stock pydantic does coercion/constraints/defaults
```

The core consumes any multidict via the `FormData` protocol — it never sees a Django request.

### Piece 2 — bound form, low-level style (L1: one call, branch once, no exceptions)

```python
def signup(request: HttpRequest) -> HttpResponse:
    form = bind(SignupForm, request)
    if form.valid:
        create_account(form.instance)          # form.instance is a typed SignupForm
        return redirect("welcome")
    return render(request, "signup.html", {"form": form})
```

`bind` is method-aware: GET yields an unbound form (defaults populate, `valid` is False), a
POST binds and validates. One branch covers first render, success, and re-render-with-errors.

### Piece 2 — valid-only style (L5: the branch disappears)

```python
@form_view(template="signup.html")
def signup(request: HttpRequest, form: SignupForm) -> HttpResponse:
    create_account(form)                       # body only runs on valid POST
    return redirect("welcome")
```

GET and invalid POST never enter the body — the adapter renders the template with the
(un)bound form in context. `form` is the pydantic instance itself, fully typed.

### Piece 3 — renderer

```django
<form method="post">
  {% formidant form %}
  <button>Sign up</button>
</form>
```

What the default template emits for one field after a failed submit (minimal by design; raw
input preserved per L2, escaped per X1):

```html
<div class="fd-field fd-invalid">
  <label for="id_email">Email</label>
  <input type="email" name="email" id="id_email" value="ada@" required>
  <p class="fd-error">value is not a valid email address</p>
</div>
```

`{% formidant_field form "email" %}` renders one field for htmx partial swaps (R4).

### The north star — ninja-style multi-source binding on a vanilla Django view (D4)

```python
@bind_view
def update_item(request: HttpRequest, item_id: int, q: str, item: Form[Item]) -> HttpResponse:
    ...
```

`item_id` binds from the URLconf kwarg, `q` from the query string, `item` from POST — the
django-ninja signature experience without django-ninja. Third-party adapters build the same
thing for their framework from the public P4 surface (protocol + introspection + error shape).

## Test design — NOT STARTED (phase 2)

Designed after acceptance criteria are accepted. Every test case names the criterion IDs it
proves; every criterion must be claimed by at least one test or explicitly marked demo-only.
R5 is a property-test candidate (hypothesis: generate model instances, round-trip).

## Pre-lock check — NOT STARTED (phase 3)

Known checks to run before locking: pydantic v2 public API surface needed for widget
resolution (`model_fields`, `FieldInfo.metadata`, annotated-types constraint objects) verified
against the installed version; Jinja2 (locked as engine — see Decisions) verified against the
installed version for R3's form/fieldset/widget override levels (ChoiceLoader/loader
precedence), autoescape guarantees for X1, and clean coexistence with Django templates.

## Decisions

- **Name: `formidant`** (mjo, 2026-07-22). PyPI free, zero GitHub collisions, unique in
  search; pydantic-lineage portmanteau. Rejected: `formwork` (73★ PHP CMS collision + common
  construction-vocabulary SEO noise), `boundform`, `formcast`.
- **Pass order: acceptance criteria → test design → build design** (mjo, 2026-07-22). This
  project pioneers the pattern; backport to the design-doc reference standard after prove-out.
- **Docstring policy: public API surface gets simple docstrings; internal modules get none;
  comment spam banned everywhere** (mjo, 2026-07-22). Matches spoe-forge practice; recorded
  globally in code-conventions.md.
- **Quality/architecture bar: spoe-forge** (mjo, 2026-07-22) — strict one-way layering, seams
  as single typed callbacks/protocols, seam vocabulary in one framework-free types module,
  registry-by-decorator extension points, per-layer exceptions converted at boundaries,
  narrow `__init__` exports, tests mirroring the source tree plus a dedicated round-trip
  suite, and an end-to-end harness against the real counterpart (for formidant: a demo Django
  app standing in for spoe-forge's real-HAProxy docker harness).
- **Default rendered markup is minimal** (mjo, 2026-07-22) — simple clean forms; Django's
  default rendering is the explicit anti-pattern.
- **Core template engine: Jinja2, as a core dependency, behind a narrow engine seam** (mjo,
  2026-07-22). Rationale: tried and tested, ubiquitous in the Python ecosystem, no reinvented
  DSL; the dependency is explicitly approved. The engine sits behind a small seam so a v2
  engine-override round is cheap and adapters can supply engines later — designed in from the
  start since the cost is low, but only Jinja2 ships in v1. Rejected: hand-rolled
  WTForms-style widget callables (reinvents template overriding poorly), adapter-supplied
  engine as the v1 mechanism (speculative flexibility before a second engine exists). Core
  dependencies are therefore exactly two: pydantic and jinja2.
- **Decorators are the v1 integration mechanism; middleware auto-binding is v2** (mjo,
  2026-07-22) — see Deferred.
- All build decisions (module layout, template engine, `Annotated` metadata vocabulary,
  bracket-parsing semantics, file-type design, error-message hook shape): **OPEN — phase 3.**

## Ticket plan — NOT STARTED (phase 3)

## Deferred / open (each gets its own future round)

- **Middleware/installed-app auto-binding — no decorators** (mjo, 2026-07-22): a Django
  `process_view` middleware could signature-sniff views and bind formidant-annotated
  parameters with zero decoration. Deferred to a possible v2 round, to be heavily tested if
  pursued — known sharp edges: mutating `view_kwargs` is a soft contract, middleware ordering,
  and per-view config (re-render template) still needs a declaration home. Decorators are the
  v1 mechanism: the Django idiom for per-view behavior (`login_required`, `csrf_exempt`).
- **Non-Django adapters (Flask/Litestar/FastHTML)** — pure sequencing; P1/P2 keep the seam.
- **i18n of error messages** — deferred; D3's override hook is the interim seam.
- **Async binding** — deferred with async adapters.
- **Widget theming packs (e.g. Tailwind/DaisyUI templates)** — deferred; R3 is the seam.
- **Template-engine override** (mjo, 2026-07-22) — v1 ships Jinja2 only, behind the engine
  seam; exposing that seam publicly for alternative engines is a v2 round.

## Key references (verified 2026-07-22)

- django-ninja source (master @ `134869b7`, 2026-07-08) — binding pipeline in
  `ninja/signature/details.py` (introspection, flatten map), `ninja/params/models.py`
  (resolve/inflate), `ninja/parser.py` (QueryDict flattening), `ninja/main.py:619` (loc→field
  error mapping). ~80–85% of binding core liftable; MIT.
- [fh-pydantic-form](https://github.com/Marcura/fh-pydantic-form) — the one live
  server-side pydantic renderer (FastHTML-locked); widget inference + htmx list-editing design
  reference.
- [fodantic](https://github.com/jpsca/fodantic) — bracket-notation form→pydantic parsing,
  checkbox handling; parsing-semantics reference.
- [FastUI issue #368](https://github.com/pydantic/FastUI/issues/368) — pydantic org's attempt,
  archived 2026-06; abandonment rationale.
- [pydantic-forms (workfloworchestrator)](https://github.com/workfloworchestrator/pydantic-forms)
  — JSON-Schema-emitting alternative path (client-rendered).
- [Personalkollen: Typed Django forms using Pydantic](https://devblog.personalkollen.se/typed-django-forms-using-pydantic.html)
  — the dual-definition drift failure mode D2 targets.
- WTForms (3.3.x) — framework-agnostic incumbent; API-shape prior art for the bound-form
  object (`form.validate()`, `form.errors`, field iteration).
