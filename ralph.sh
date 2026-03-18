#!/bin/bash
# Ralph Loop — fresh context window per iteration
# Usage: ./ralph.sh [max_iterations]

# ── 설정 ─────────────────────────────────────────────────────────────
MAX_ITERATIONS=${1:-15}
SLEEP_BETWEEN=10
RALPH_DIR=".ralph"
CURRENT_DIR="$RALPH_DIR/current"
ARCHIVE_DIR="$RALPH_DIR/archive"
LOG_FILE="$RALPH_DIR/ralph-$(date +%Y%m%d-%H%M%S).log"

# ── 색상 ─────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'
YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'
log() { echo -e "$1" | tee -a "$LOG_FILE"; }

# ── 사전 체크 ─────────────────────────────────────────────────────────
if ! command -v claude &>/dev/null; then
  echo -e "${RED}❌ Claude Code CLI 미설치${NC}"
  echo "   npm install -g @anthropic-ai/claude-code"
  exit 1
fi
if [[ ! -f "$CURRENT_DIR/PRD.md" ]]; then
  echo -e "${RED}❌ .ralph/current/PRD.md 없음 — /ralph-set 먼저 실행하세요${NC}"
  exit 1
fi
if [[ ! -f "$CURRENT_DIR/PROMPT.md" ]]; then
  echo -e "${RED}❌ .ralph/current/PROMPT.md 없음 — /ralph-set 먼저 실행하세요${NC}"
  exit 1
fi

# ── 루프 진입 전 조기 완료 체크 (Fix 8) ─────────────────────────────
REMAINING=$(grep -cE "^\- \[ \]" "$CURRENT_DIR/PRD.md" 2>/dev/null || true)
[[ -z "$REMAINING" ]] && REMAINING=0
if [[ "$REMAINING" -eq 0 ]]; then
  log "${YELLOW}⚠️ 모든 태스크가 이미 완료 상태입니다. 아카이브 후 종료합니다.${NC}"
  FEATURE_NAME=$(head -1 "$CURRENT_DIR/PRD.md" \
    | sed 's/# 피쳐: //' | tr ' ' '-' | sed 's/[^a-zA-Z0-9가-힣-]//g')
  ARCHIVE_TARGET="$ARCHIVE_DIR/$(date +%Y-%m-%d)_${FEATURE_NAME}_already-done"
  mkdir -p "$ARCHIVE_TARGET"
  cp "$CURRENT_DIR/PRD.md" "$CURRENT_DIR/PROMPT.md" "$ARCHIVE_TARGET/" 2>/dev/null || true
  [[ -f "$CURRENT_DIR/progress.txt" ]] && cp "$CURRENT_DIR/progress.txt" "$ARCHIVE_TARGET/" || true
  rm -f "$CURRENT_DIR/PRD.md" "$CURRENT_DIR/PROMPT.md" "$CURRENT_DIR/progress.txt"
  exit 0
fi

# ── progress.txt 초기화 ──────────────────────────────────────────────
if [[ ! -f "$CURRENT_DIR/progress.txt" ]]; then
  cat > "$CURRENT_DIR/progress.txt" << EOF
# Ralph Progress Log
시작: $(date)
브랜치: $(git branch --show-current 2>/dev/null || echo "unknown")
---

EOF
fi

# ── 피쳐명 추출 ─────────────────────────────────────────────────────
FEATURE_NAME=$(head -1 "$CURRENT_DIR/PRD.md" \
  | sed 's/# 피쳐: //' | tr ' ' '-' | sed 's/[^a-zA-Z0-9가-힣-]//g')

# ── 메인 루프 ───────────────────────────────────────────────────────
ITERATION=0
log ""
log "${BOLD}${BLUE}╔══════════════════════════════════════════╗${NC}"
log "${BOLD}${BLUE}║           Ralph Loop 시작                ║${NC}"
log "${BOLD}${BLUE}╚══════════════════════════════════════════╝${NC}"
log "  브랜치:   $(git branch --show-current 2>/dev/null || echo 'unknown')"
log "  피쳐:     $FEATURE_NAME"
log "  최대반복: $MAX_ITERATIONS"
log "  로그:     $LOG_FILE"

while [[ $ITERATION -lt $MAX_ITERATIONS ]]; do
  ITERATION=$((ITERATION + 1))

  # 태스크 상태 카운트 — grep 실패해도 스크립트 유지 (Fix 2)
  REMAINING=$(grep -cE "^\- \[ \]" "$CURRENT_DIR/PRD.md" 2>/dev/null || true)
  [[ -z "$REMAINING" ]] && REMAINING=0
  DONE_COUNT=$(grep -cE "^\- \[x\]" "$CURRENT_DIR/PRD.md" 2>/dev/null || true)
  [[ -z "$DONE_COUNT" ]] && DONE_COUNT=0
  BLOCKED_COUNT=$(grep -c "BLOCKED" "$CURRENT_DIR/PRD.md" 2>/dev/null || true)
  [[ -z "$BLOCKED_COUNT" ]] && BLOCKED_COUNT=0

  log ""
  log "${BLUE}──────────────────────────────────────────${NC}"
  log "${BOLD}📍 Iteration $ITERATION/$MAX_ITERATIONS${NC}  |  $(date '+%H:%M:%S')"
  log "   태스크: ${GREEN}완료 $DONE_COUNT${NC} | ${YELLOW}남음 $REMAINING${NC} | ${RED}블로킹 $BLOCKED_COUNT${NC}"
  log "${BLUE}──────────────────────────────────────────${NC}"

  # 핵심: stdin redirect 방식 (-p 대신 --print + 리디렉션) (Fix 1)
  # set -e 일시 비활성화로 Claude 오류가 스크립트를 죽이지 않도록 (Fix 3)
  set +e
  OUTPUT=$(claude --print --dangerously-skip-permissions \
    < "$CURRENT_DIR/PROMPT.md" 2>&1 | tee -a "$LOG_FILE")
  CLAUDE_EXIT=$?
  set -e

  # Claude 오류 처리
  if [[ $CLAUDE_EXIT -ne 0 ]]; then
    log "${YELLOW}⚠️  Claude 종료 코드: $CLAUDE_EXIT — 계속 진행${NC}"
  fi

  # 완료 체크 — BLOCKED 오인식 방지 포함 (Fix 6)
  if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
    TOTAL=$(( DONE_COUNT + REMAINING ))
    if [[ "$BLOCKED_COUNT" -gt 0 && "$BLOCKED_COUNT" -eq "$TOTAL" ]]; then
      log ""
      log "${RED}❌ 모든 태스크($TOTAL개)가 BLOCKED 상태입니다.${NC}"
      log "   .ralph/current/progress.txt 를 확인하고 수동으로 해결하세요."
      exit 2
    fi

    log ""
    log "${GREEN}╔══════════════════════════════════════════╗${NC}"
    log "${GREEN}║        ✅ 피쳐 개발 완료!               ║${NC}"
    log "${GREEN}╚══════════════════════════════════════════╝${NC}"
    log "  총 반복: $ITERATION 회"
    log ""
    log "📋 최종 PRD 상태:"
    # grep 실패 방지 (Fix 2)
    grep -E "^\- \[" "$CURRENT_DIR/PRD.md" | tee -a "$LOG_FILE" || true
    log ""
    log "📝 progress.txt 마지막 기록:"
    tail -20 "$CURRENT_DIR/progress.txt" | tee -a "$LOG_FILE" || true
    log ""

    # 완료 아카이브 — CLAUDE.md 스냅샷 포함 (Fix 11)
    ARCHIVE_TARGET="$ARCHIVE_DIR/$(date +%Y-%m-%d)_${FEATURE_NAME}"
    mkdir -p "$ARCHIVE_TARGET"
    cp "$CURRENT_DIR/PRD.md" \
       "$CURRENT_DIR/PROMPT.md" \
       "$CURRENT_DIR/progress.txt" \
       "$ARCHIVE_TARGET/" 2>/dev/null || true
    cp "$LOG_FILE" "$ARCHIVE_TARGET/" 2>/dev/null || true
    [[ -f "CLAUDE.md" ]] && cp CLAUDE.md "$ARCHIVE_TARGET/CLAUDE.md.snapshot" || true
    rm -f "$CURRENT_DIR/PRD.md" \
          "$CURRENT_DIR/PROMPT.md" \
          "$CURRENT_DIR/progress.txt"

    log "📦 아카이브: $ARCHIVE_TARGET"
    log ""
    log "${GREEN}💡 다음 단계:${NC}"
    log "   git push origin $(git branch --show-current 2>/dev/null)"
    log "   → PR 생성"
    exit 0
  fi

  # BLOCKED 경고
  if [[ "$BLOCKED_COUNT" -gt 0 ]]; then
    log "${YELLOW}⚠️  블로킹 태스크 ${BLOCKED_COUNT}개 — .ralph/current/progress.txt 확인 권장${NC}"
  fi

  log ""
  log "⏸  ${SLEEP_BETWEEN}초 후 다음 iteration..."
  sleep $SLEEP_BETWEEN
done

log ""
log "${RED}⚠️  최대 반복(${MAX_ITERATIONS})에 도달했습니다.${NC}"
log "남은 태스크:"
grep -E "^\- \[ \]" "$CURRENT_DIR/PRD.md" | tee -a "$LOG_FILE" || true
log ""
log "추가 실행: ./ralph.sh [횟수]"
exit 1
