# Profile & Lock UX / Security TODOs

This document organizes planned work for user profile features and lock/unlock UX/security improvements by priority and phase. Each item includes a short description, acceptance criteria, related files, and estimated effort.

---

## Phase 1 — High priority ✅
Goal: Improve user-facing lock messages and admin visibility of lock metadata so the system is clear and actionable.

- [x] Login: Friendly locked-account message
  - Description: Replace raw minute counts with a localized unlock time + human-readable duration. Add optional CTA to contact admin.
  - Acceptance: Login attempts on locked accounts show message like "Compte verrouillé jusqu'au 22/12/2025 23:30 (1 heure). Contactez un administrateur pour assistance." No lock reason shown.
  - Files: `src/auth.py`, `templates/auth/login.html`
  - Effort: 1h

- [x] Ensure automatic locks store metadata (reason, who (null), when)
  - Description: When automatic lock occurs (failed attempts), set `verrouille_raison='trop de tentatives'`, `verrouille_le`, and keep `verrouille_par_id` null.
  - Acceptance: Admins can see reason "trop de tentatives" in user detail. Audit log recorded.
  - Files: `src/auth.py`, `src/models.py`, DB migration
  - Effort: 1h


- [ ] Admin UI: show lock metadata on user detail (who, when, reason, unlock time)
  - Description: Add/verify UI elements in `templates/users/view.html` to show `verrouille_raison`, `verrouille_par_id (name)`, `verrouille_le` (localized), and `verrouille_jusqu_a` (localized).
  - Acceptance: Admin sees all metadata; normal users do not see reasons of other users (role gating).
  - Files: `templates/users/view.html`, `src/users.py`
  - Effort: 1h (mostly done, verify role gating)

- [x] Users list: show lock status + tooltip for admins
  - Description: In `templates/users/list.html` show a badge for locked users; admins see a tooltip with unlock local time and truncated reason.
  - Acceptance: Admin hover shows reason (<= 150 chars) and unlock time. Tooltip sanitized.
  - Files: `templates/users/list.html`, `src/users.py`
  - Effort: 45m

- [ ] Admin flash message when manually locking an account includes readable duration and local unlock time
  - Description: Flash message for admin after locking must be friendly and include the reason when provided.
  - Acceptance: Example: "Utilisateur operateur verrouillé jusqu'au 22/12/2025 23:30 (1 heure). Raison: Investigation." (Reason optional)
  - Files: `src/users.py`
  - Effort: 15m

---

## Phase 2 — Medium priority 🟡
Goal: Add a secure Profile page allowing users to manage personal info and change password.

- [ ] Add profile view & edit (`GET`/`POST` `/profile`)
  - Description: Allow editing display name only (username immutable by default). Validate inputs, audit log on change.
  - Acceptance: Users can update display name; audit log `MODIFICATION_PROFIL_UTILISATEUR` is created (fields changed listed), success flash shown.
  - Files: `src/users.py` (new route), `templates/users/profile.html`
  - Effort: 2h

- [ ] Add change password form on profile page
  - Description: Require `current_password`, `new_password`, `confirm_password`. Enforce min length (6); verify current password with bcrypt; log success/failure.
  - Acceptance: Password update requires correct current password; `MODIFICATION_MOT_DE_PASSE_UTILISATEUR` logged; invalid attempts logged with `ECHEC_MODIFICATION_MOT_DE_PASSE_UTILISATEUR`.
  - Files: `src/users.py`, `templates/users/profile.html`
  - Effort: 2h

- [ ] UI: Add "Mon profil" link in header + mobile menu
  - Description: Add a link in `templates/base.html` visible for logged-in users.
  - Acceptance: Link present and navigates to `/profile`.
  - Files: `templates/base.html`
  - Effort: 15m

- [ ] Tests for profile and password change flows
  - Files: `tests/test_users_profile.py`
  - Effort: 2h

---

## Phase 3 — Useful / Admin features 🟢
Goal: Provide better tools for admins and auditability.

- [ ] Lock/Unlock history / audit view per user
  - Description: Create a user-level view that shows lock/unlock events (from the audit journal) with time and reason.
  - Acceptance: Admin can view a timeline of lock-related audit actions.
  - Files: `templates/users/view.html`, `src/audit_logger.py`, `src/users.py`
  - Effort: 3h

- [ ] Optional: Email notification when account is locked/unlocked
  - Acceptance: Email templates created; toggle in config.
  - Files: `src/notifications.py` (new), config updates
  - Effort: 3-5h

---

## Phase 4 — Future / Enhancements 🔮
Goal: Strengthen security and scalability.

- [ ] 2FA for ADMIN/SUPERADMIN (optional)
- [ ] Rate-limiting login attempts by IP + user
- [ ] Password strength checker + disallow common passwords

---

## Migration & Testing notes
- DB: Add new columns (`verrouille_raison`, `verrouille_par_id`, `verrouille_le`) — use Alembic for production migrations. In this repo we used destructive `rebuild_db.sh` for dev.
- Tests: Cover login, lock/unlock, admin lock/unlock, profile edits, and audit entries.
- Security: Never display lock reasons on the public login page; only show to admins.

---

## Next recommended step
- Start Phase 1 tasks (login message + ensure auto-lock metadata + admin UI bits). I can implement and add tests in the next commit.

---

If you'd like, I can now implement the profile page (Phase 2 start) or finish any remaining Phase 1 items — which should I start with?