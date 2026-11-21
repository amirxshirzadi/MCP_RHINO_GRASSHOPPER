---
name: valider
description: Enregistre (commit) et publie (push) sur GitHub les modifications que l'utilisateur vient de valider.
argument-hint: "[message de commit facultatif]"
disable-model-invocation: true
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git push:*), Bash(git log:*), Bash(git branch:*), PowerShell(git status*), PowerShell(git diff*), PowerShell(git add*), PowerShell(git commit*), PowerShell(git push*), PowerShell(git log*), PowerShell(git branch*)
---

L'utilisateur a relu et validé les modifications en cours. Enregistre-les et publie-les sur GitHub.

1. Lance `git status --short` et `git diff --stat` (ainsi que `git diff --cached --stat`) pour voir ce qui a changé.
   S'il n'y a aucune modification, dis-le et arrête-toi.
2. Vérifie qu'aucun fichier sensible n'est inclus (`.env`, clés, jetons, `credentials*`, `.claude/settings.local.json`).
   S'il y en a, ne les ajoute pas et préviens l'utilisateur.
3. `git add -A`
4. Message de commit :
   - si l'utilisateur a fourni un message ($ARGUMENTS), utilise-le tel quel comme titre ;
   - sinon, rédige un titre court en français, à l'impératif, qui résume les changements (par ex. « Ajoute l'outil de création de courbes »).
   Termine le message par une ligne vide puis la ligne d'attribution de commit prévue pour cette session, s'il y en a une.
5. `git commit`, puis `git push` (avec `-u origin <branche>` si la branche n'a pas encore d'amont).
6. Réponds en une ou deux lignes : le titre du commit, son hash court, et confirme que le push a réussi.
   Si le push échoue, montre l'erreur et ne retente pas en forçant.
