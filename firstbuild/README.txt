Study Invaders - README

Files created:
 - space_quiz_game.py    (the game script)
 - questions.csv         (sample CSV with a few questions)

How to run locally:
 1) Make sure you have Python 3.8+ installed.
 2) Install pygame: pip install pygame
 3) Copy both files to the same folder, or run space_quiz_game.py from the folder containing questions.csv
 4) Run: python space_quiz_game.py

CSV format (header required):
id,question,answer,subject,difficulty

Distractor generation (MVP):
 - Numeric answers: +/- 1, +2, etc.
 - Text answers: pulled from other 'answer' values in the CSV where possible

Notes:
 - This is an MVP prototype. The game shows a question; clicking the correct choice causes your ship to fire a bullet.
 - Expand distractor logic, add animations, sound, and polish as needed.
