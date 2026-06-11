# ============================================================
# .claude/prefs.d/ — Project Preference Drop-in Directory
# ============================================================
#
# PURPOSE
# -------
# This directory holds drop-in preference files that extend
# specific law behaviors for this project. Think of it as
# /etc/systemd/system/law.N.d/ — overrides and extensions
# that live next to the constitutional units without touching
# them.
#
# WHEN TO USE PREFS.D VS PROJECT.CONF
# ------------------------------------
# project.conf  → global project preferences (git, cascade,
#                 ladder, session behavior). Claude writes here
#                 when you state a persistent preference.
#
# prefs.d/      → structured extensions to specific laws.
#                 Use when you want to formally extend a law's
#                 ascending (check) or descending (cascade)
#                 behavior with project-specific logic.
#
# FILE NAMING
# -----------
# law.N.d.conf       → extends law N's behavior
# project-NAME.conf  → named preference bundle (loaded always)
#
# Examples already here:
#   law.27.d.conf    → extra ladder rungs for this project
#   law.26.d.conf    → extra cascade targets for this project
#
# HOW CLAUDE USES THESE FILES
# ----------------------------
# At session start, law-manage.py reads all *.conf files in
# this directory and merges them with project.conf. Drop-ins
# take precedence over project.conf for same keys. Constitutional
# .init/ units are never touched.
#
# HOW TO CREATE A DROP-IN
# ------------------------
# 1. Create a .conf file here (name it descriptively)
# 2. Use the same INI format as project.conf
# 3. Only specify keys you want to override/extend — others
#    inherit from project.conf and constitutional defaults
#
# EXAMPLE: Aggressive git behavior for a CI/CD project
#
#   # prefs.d/project-cicd.conf
#   [git]
#   COMMIT_ON_TASK_COMPLETE = true
#   AUTO_PUSH = true
#
# EXAMPLE: Extra ladder rungs for an API project
#
#   # prefs.d/law.27.d.conf
#   [ladder]
#   EXTRA_RUNGS = Verify all endpoints in api.yaml have a test; Check OpenAPI spec validates
#
# ============================================================
