(function () {
  const form = document.getElementById('task-form');
  if (!form) return;

  const answerInput = document.getElementById('user_answer');
  const submitBtn = document.getElementById('submit-btn');
  const startField = document.getElementById('client_start_ts');
  const submitField = document.getElementById('client_submit_ts');
  const rtField = document.getElementById('rt_ms');
  const visField = document.getElementById('visibility_events');
  const statusText = document.getElementById('status-text');

  const correctAnswer = Number(form.dataset.correctAnswer);
  const minDelayMs = 250;

  const startTs = Date.now();
  let visibilityCount = 0;
  let canSubmit = false;
  let submitted = false;

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

  function maybeAutoSubmit() {
    if (submitted || !canSubmit) {
      return;
    }

    const raw = answerInput.value.trim();
    if (raw.length === 0) {
      statusText.textContent = 'Waiting for correct answer…';
      return;
    }

    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
      statusText.textContent = 'Enter an integer answer.';
      return;
    }

    if (parsed !== correctAnswer) {
      statusText.textContent = 'Incorrect. Keep trying.';
      return;
    }

    submitted = true;
    statusText.textContent = 'Correct! Loading next problem…';

    const submitTs = Date.now();
    submitField.value = String(submitTs);
    rtField.value = String(submitTs - startTs);
    submitBtn.disabled = true;

    form.requestSubmit();
  }

  answerInput.addEventListener('input', maybeAutoSubmit);
  answerInput.addEventListener('change', maybeAutoSubmit);

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
