(function () {
  const form = document.getElementById('task-form');
  if (!form) return;

  const answerInput = document.getElementById('user_answer');
  const submitBtn = document.getElementById('submit-btn');
  const startField = document.getElementById('client_start_ts');
  const submitField = document.getElementById('client_submit_ts');
  const rtField = document.getElementById('rt_ms');
  const visField = document.getElementById('visibility_events');
  const stopForm = document.getElementById('stop-form');

  const correctAnswer = Number(form.dataset.correctAnswer);
  const minDelayMs = 250;
  const inactivityLimitMs = 5 * 60 * 1000;

  const startTs = Date.now();
  let visibilityCount = 0;
  let canSubmit = false;
  let submitted = false;
  let inactivityTimer = null;

  startField.value = String(startTs);

  setTimeout(() => {
    canSubmit = true;
  }, minDelayMs);

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      visibilityCount += 1;
      visField.value = String(visibilityCount);
    }
  });

  function restartInactivityTimer() {
    if (!stopForm || submitted) {
      return;
    }
    if (inactivityTimer) {
      clearTimeout(inactivityTimer);
    }
    inactivityTimer = setTimeout(() => {
      if (!submitted) {
        stopForm.requestSubmit();
      }
    }, inactivityLimitMs);
  }

  function maybeAutoSubmit() {
    if (submitted || !canSubmit) {
      return;
    }

    const raw = answerInput.value.trim();
    if (raw.length === 0) {
      return;
    }

    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
      return;
    }

    if (parsed !== correctAnswer) {
      return;
    }

    submitted = true;
    if (inactivityTimer) {
      clearTimeout(inactivityTimer);
    }

    const submitTs = Date.now();
    submitField.value = String(submitTs);
    rtField.value = String(submitTs - startTs);
    submitBtn.disabled = true;

    form.requestSubmit();
  }

  answerInput.addEventListener('input', maybeAutoSubmit);
  answerInput.addEventListener('change', maybeAutoSubmit);
  ['input', 'keydown', 'pointerdown', 'mousemove', 'touchstart', 'scroll'].forEach((eventName) => {
    document.addEventListener(eventName, restartInactivityTimer, { passive: true });
  });

  restartInactivityTimer();

  form.addEventListener('submit', function () {
    if (submitted) {
      return;
    }

    // Fallback if submit is triggered manually.
    const submitTs = Date.now();
    submitField.value = String(submitTs);
    rtField.value = String(submitTs - startTs);
  });
})();
