#!/bin/bash
PORT=8090
OUTDIR="/home/z/my-project/magnific/downloads"
LOGDIR="/home/z/my-project/magnific/test_results"
mkdir -p "$LOGDIR"

NUM=${1:-7}
echo "========================================"
echo "  Testing $NUM concurrent image requests"
echo "  Port: $PORT"
echo "========================================"

PROMPTS=(
  "A golden dragon flying over medieval castle at sunset"
  "Cyberpunk city street at night with neon lights"
  "Cute cat wearing a tiny hat sitting in a coffee shop"
  "Futuristic sports car on a highway with mountains"
  "Underwater coral reef with colorful tropical fish"
  "Astronaut planting a flag on Mars surface"
  "Japanese cherry blossom garden with a red bridge"
  "Magical forest with glowing mushrooms at twilight"
  "Vintage robot playing piano in a jazz bar"
  "Crystal palace floating above the clouds"
  "Desert oasis with palm trees under starry sky"
  "Steampunk airship flying over Victorian London"
  "Wolf howling at northern lights aurora borealis"
  "Tropical waterfall hidden in lush jungle"
  "Abstract colorful fluid art in 4k resolution"
)

echo ""
echo "Launching $NUM requests..."

for i in $(seq 1 $NUM); do
  PROMPT="${PROMPTS[$((i-1))]}"
  OUTPUT="$LOGDIR/concurrent_${i}.json"
  
  curl -s -X POST "http://localhost:$PORT/api/image/generate" \
    -H "Content-Type: application/json" \
    -d "{
      \"prompt\": \"$PROMPT\",
      \"model\": \"imagen-nano-banana-2\",
      \"aspect_ratio\": \"1:1\",
      \"resolution\": \"2k\",
      \"wait\": true,
      \"download\": false
    }" \
    -o "$OUTPUT" \
    -w "{\"req\":$i,\"http_code\":%{http_code},\"time\":%{time_total}}\n" \
    -H "X-Request-ID: req-$i" &>/dev/null &

  echo "  [Req $i] Launched: $PROMPT"
done

echo ""
echo "All $NUM requests launched. Waiting for completions..."
wait
echo ""
echo "========================================"
echo "  RESULTS"
echo "========================================"

SUCCESS=0
FAIL=0
TOTAL_TIME=0

for i in $(seq 1 $NUM); do
  FILE="$LOGDIR/concurrent_${i}.json"
  if [ -f "$FILE" ]; then
    STATUS=$(python3 -c "import json; d=json.load(open('$FILE')); print(d.get('status','?'))" 2>/dev/null)
    SUCCESS_STR=$(python3 -c "import json; d=json.load(open('$FILE')); print(d.get('success','?'))" 2>/dev/null)
    ELAPSED=$(python3 -c "import json; d=json.load(open('$FILE')); print(d.get('elapsed','?'))" 2>/dev/null)
    CREATION_ID=$(python3 -c "import json; d=json.load(open('$FILE')); print(d.get('creation_id','?'))" 2>/dev/null)
    
    if [ "$SUCCESS_STR" = "True" ] && ([ "$STATUS" = "completed" ] || [ "$STATUS" = "processing" ]); then
      echo "  [Req $i] ✅ SUCCESS — status=$STATUS elapsed=${ELAPSED}s creation_id=$CREATION_ID"
      SUCCESS=$((SUCCESS+1))
    else
      MSG=$(python3 -c "import json; d=json.load(open('$FILE')); print(d.get('message','?'))" 2>/dev/null)
      echo "  [Req $i] ❌ FAIL — status=$STATUS message=$MSG"
      FAIL=$((FAIL+1))
    fi
  else
    echo "  [Req $i] ❌ NO RESPONSE"
    FAIL=$((FAIL+1))
  fi
done

echo ""
echo "========================================"
echo "  SUMMARY: $SUCCESS/$NUM succeeded, $FAIL/$NUM failed"
echo "========================================"
