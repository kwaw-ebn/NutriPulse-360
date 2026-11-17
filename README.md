# NutriPulse 360

**District Health Performance & Accountability System**

Track Performance. Drive Action. Improve Health.

Developed by **Ebenezer Kwaw | EK Synergy Ltd** for Agona East District Health Directorate, Ghana Health Service.

## MVP capabilities

- Responsive React/TypeScript officer workspace with original EK Synergy logo.
- FastAPI + SQLAlchemy + Alembic; Neon PostgreSQL persistence.
- District, subdistrict and facility roles, server-enforced reporting scopes.
- Password hashing (scrypt), HTTP-only expiring cookies, CSRF tokens, login throttling and password change with session invalidation.
- Core nutrition aggregate reporting: breastfeeding, growth monitoring, Vitamin A, anaemia, IYCF and rehabilitation; Wellness Clinic reporting matching the uploaded Registrants, Attendance, Screening outcomes and Interventions/services tables, with compilation and certification details.
- Draft → submitted → approved / returned workflow. A second district officer approves an author's report.
- Indicator-specific cumulative calculations, lower-is-better assessment, annual and six-month milestones. Ratios use summed numerators and denominators, never averages of facility rates.
- Seven-field mandatory corrective action plans on below-target or missing-measure results; persistent actions across reporting periods; district closure and complete follow-up history.
- Approved-data dashboards, monthly reporting completeness, trends, facility comparisons, Excel/PDF exports and audit activity.
- 25 facilities across Asafo, Duakwa/Mensakrom, Kwanyako, Mankrong and Nsaba, imported from the supplied 2025 workbook.

## Facility target counts

The dashboard omits district population and facility-scope summary cards. Its facility comparison lists the annual stunting assessment and six-month Vitamin A counts for every facility, even before reports exist. Each uses that facility's uploaded under-five or 6–59 month population, multiplied by 10% or 80%. Counts and elapsed-period milestones round up to whole children. Missing reports remain missing performance. Clinical ratios retain their report-based denominators; lower-is-better maximum count thresholds round down. Excel exports include a Facility targets sheet.

## Source data decisions

The approved district population is **108,787** for **2025**. Facility populations sum to **108,768**; Sheet1's district total is **108,767**. Imported facility age-group populations are preserved from Sheet2 (under-five and 6–59 month columns) and are not silently reconciled. Several workbook cells have inconsistent age-group calculations. A district data officer must approve corrections before operational use. No annual population growth rate is assumed.

Wellness indicator **3.31** uses only the designated District Hospital Wellness Clinic and an administrator-approved eligible population. Its denominator starts unset. Administrators can explicitly approve 108,787 if the entire district is the eligible group. Wellness submission is blocked until a denominator is approved.

The nutrition template records breastfeeding within **3 minutes**, while indicator 1.16 requires **1 hour**. These are separate fields. One-hour initiation must include the three-minute subset.

Diabetes and hypertension targets are supplied as **1–5** and **5–10** without confirmed units. OPD counts are descriptive only; these indicators are not assigned pass/fail scores.

### Calculation definitions

| Code | Numerator | Denominator | Threshold / period |
|---|---|---|---|
| 1.16 | Babies breastfed within one hour | Facility deliveries | ≥95%, cumulative ratio |
| 2.4 | New unique U5 children measured each month, summed year-to-date | Imported U5 population | ≥10% annually, linear month/12 milestone |
| 2.5 | Women with Hb <11 g/dL at 36 weeks | Women Hb-checked at 36 weeks | ≤35.5%, cumulative ratio |
| 2.6 | New unique 6–59 month children dosed within the current half-year | Imported 6–59 month population | ≥80% per Jan–Jun / Jul–Dec round, linear elapsed-round milestone |
| 2.9 | Moderate + severe underweight attendance | Total weighed attendance | ≤3.8%, cumulative ratio |
| 3.31 | New unique eligible attendees in the designated clinic, summed year-to-date | Administrator-approved eligible population | ≥20% annually, linear month/12 milestone |

Unique counters require register-based deduplication before data entry. Aggregate-only data cannot independently detect repeated people across months. Attendance-based growth figures must be interpreted as service reporting measures, not deduplicated population prevalence estimates. Target definitions and linear milestone assumptions need district sign-off.

## Local development

Python 3.12+ and Node 22+.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
# Export DATABASE_URL, DATABASE_URL_UNPOOLED, JWT_SECRET,
# ADMIN_EMAIL and ADMIN_PASSWORD securely before starting.
# SQLite is supported locally when DATABASE_URL is absent.
export COOKIE_SECURE=false
alembic upgrade head
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to localhost:8000. API docs: `/docs`. Health: `/health`.

```bash
cd backend
python -m pytest -q
cd ../frontend
npm ci
npm run build
```

## Deploy to Render + Neon

1. Create a dedicated Neon project and database. Use a pooled connection for `DATABASE_URL` and its direct counterpart for `DATABASE_URL_UNPOOLED`. Require SSL. Keep credentials exclusively in Render's secret environment variables.
2. Deploy this repository's `render.yaml` as a Render Blueprint. The plan uses a free Python web service and a static frontend. Review availability and any account charges before applying.
3. Provide the two Neon URLs and `ALLOWED_ORIGINS` as the exact HTTPS frontend origin. JWT and initial administrator password are generated by Render.
4. **Before applying**, verify final service URLs in the plan. Blueprint creation may suffix service names. Update the frontend `/api/*` rewrite to the actual API HTTPS URL if it differs from `https://nutripulse-360-api.onrender.com/api/*` and set `ALLOWED_ORIGINS` to the final frontend URL.
5. Backend starts by running `alembic upgrade head` over the direct connection, then listens on `0.0.0.0:$PORT`. This startup migration strategy is for a single-instance free MVP. For scaled or paid production deployments, move migration into a controlled pre-deploy job with locking.
6. Verify backend `/health` and frontend sign-in, not just deploy status. The same-origin API rewrite avoids reliance on third-party cookies. If choosing separate-origin API requests instead, set `VITE_API_URL`, keep exact CORS origins, and validate browser cookie policy.
7. Retrieve the initial password securely from the API service's `ADMIN_PASSWORD` value in the Render dashboard. Initial officer email: `ekwaw4545@gmail.com`. Change the password on first use in Administration. The bootstrap password never overwrites an existing account.
8. Approve Wellness Clinic configuration and create facility/subdistrict officers and a separate district reviewer. Pilot with synthetic registers first.

Free Render services may sleep after inactivity and take time to wake up. Database durability is supplied by Neon; Render's filesystem is not used to persist health reports.

## Limits before operational rollout

This is an MVP, not a production-readiness certification. The complete immunization, school-health, commodities and detailed age/sex breakdown sections in the original nutrition worksheet are not yet implemented. Population editing/import reconciliation, approved projections, scheduled notifications, email password reset, deactivation UI and backup/restore drills remain rollout work. Review district data governance, finalize denominator definitions, configure backup retention and test recovery with the hosting owner before entering real operational data. Do not enter patient names, phone numbers or identifiers in free-text fields.

## Wellness Clinic source format

The Wellness Clinic form follows `REPORTING FORMAT FOR WELLNESS CLINIC(1).docx`: separate registrants and attendance tables for diabetes, hypertension, height, weight, BMI, skin diseases, anaemia and others; male/female moderate, severe and normal outcomes for diabetes, hypertension, BMI, anaemia and others; counselling, referral, therapy and other services with remarks; reporting date, compiled by, phone and certified by. Totals are calculated from entered rows. Source spelling errors are corrected in labels without changing categories. Outcome classifications come from registers, not automated clinical diagnosis. Screening totals may include multiple services for one person and never substitute for deduplicated annual attendance in indicator 3.31. Aggregate form metadata is stored within the existing report JSON; no schema migration or report deletion is required.
