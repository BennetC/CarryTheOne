(function () {
  const form = document.getElementById('task-form');
  if (!form) return;

  const submitBtn = document.getElementById('submit-btn');
  const startField = document.getElementById('client_start_ts');
  const submitField = document.getElementById('client_submit_ts');
  const rtField = document.getElementById('rt_ms');
  const visField = document.getElementById('visibility_events');

  let startTs = Date.now();
  let visibilityCount = 0;

  startField.value = String(startTs);

  setTimeout(() => {
    submitBtn.disabled = false;
  }, 250);

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      visibilityCount += 1;
      visField.value = String(visibilityCount);
    }
  });

  form.addEventListener('submit', function () {
    const submitTs = Date.now();
    submitField.value = String(submitTs);
    rtField.value = String(submitTs - startTs);
    submitBtn.disabled = true;
  });
})();
