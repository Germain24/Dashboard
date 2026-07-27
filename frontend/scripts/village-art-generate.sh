#!/bin/bash
# Génère les visuels du village via Codex (image_gen).
# Reprend là où il s'est arrêté : une image déjà présente n'est pas régénérée.
# Chemin normalisé en POSIX : `xargs` traite l'antislash comme un caractère
# d'échappement, si bien qu'un chemin Windows brut ressort en « C:Usersgerma… »
# et que tous les `cat` renvoient du vide — les prompts partaient vides.
W=$(cygpath -u "$1" 2>/dev/null || echo "$1")
PAR="${2:-6}"
mkdir -p "$W/png" "$W/log"

gen() {
  local f="$1"
  local name
  name=$(basename "$f" .txt)
  local out="$W/png/$name.png"
  if [ -s "$out" ]; then
    echo "SKIP $name"
    return 0
  fi
  local try
  for try in 1 2 3; do
    timeout 420 codex exec -C "$W/png" -s workspace-write --skip-git-repo-check \
      'Use the image generation tool ($imagegen) to generate: '"$(cat "$f")"' Save it as ./'"$name"'.png. Do not do anything else.' \
      >"$W/log/$name.log" 2>&1
    if [ -s "$out" ]; then
      echo "OK $name (essai $try)"
      return 0
    fi
    sleep 3
  done
  echo "FAIL $name"
  return 1
}

export -f gen
export W

ls "$W/prompts"/*.txt | xargs -P "$PAR" -I{} bash -c 'gen "$@"' _ {}
echo "=== TERMINE : $(ls "$W/png"/*.png 2>/dev/null | wc -l) images ==="
