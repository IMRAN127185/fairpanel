/**
 * FairPanel - Participant Project Submission Wizard
 * 4 Steps: Basics -> Details -> Links and Media -> Review.
 * Handles auto/manual save draft, version conflict resolution, and final submission.
 */

document.addEventListener('DOMContentLoaded', () => {
  const wizard = document.getElementById('submission-wizard');
  if (!wizard) return;

  const eventId = wizard.dataset.eventId;
  let projectId = wizard.dataset.projectId || null;
  let projectVersion = parseInt(wizard.dataset.projectVersion || '1', 10);
  let isDirty = false;

  const steps = ['basics', 'details', 'links', 'review'];
  let currentStepIdx = 0;

  const stepTabs = document.querySelectorAll('.wizard-step');
  const stepPanels = document.querySelectorAll('.step-panel');
  const btnPrev = document.getElementById('wizard-prev');
  const btnNext = document.getElementById('wizard-next');
  const btnSave = document.getElementById('btn-save-draft');
  const btnSubmit = document.getElementById('btn-submit-project');

  function showStep(idx) {
    currentStepIdx = idx;
    stepTabs.forEach((tab, i) => {
      tab.classList.toggle('active', i === idx);
      if (i < idx) tab.classList.add('completed');
    });
    stepPanels.forEach((panel, i) => {
      panel.style.display = i === idx ? 'block' : 'none';
    });

    btnPrev.style.display = idx === 0 ? 'none' : 'inline-flex';
    btnNext.style.display = idx === steps.length - 1 ? 'none' : 'inline-flex';

    if (idx === steps.length - 1) {
      updateReviewSummary();
    }
  }

  function collectFormData() {
    const form = document.getElementById('submission-form');
    if (!form) return {};

    const formData = new FormData(form);
    const data = {
      title: formData.get('title') || '',
      tagline: formData.get('tagline') || '',
      description: formData.get('description') || '',
      track_id: formData.get('track_id') || '',
      thumbnail_url: formData.get('thumbnail_url') || '',
      repo_url: formData.get('repo_url') || '',
      live_url: formData.get('live_url') || '',
      video_url: formData.get('video_url') || '',
      tech_tags: (formData.get('tech_tags') || '').split(',').map(s => s.trim()).filter(Boolean),
      custom_answers: {},
      version: projectVersion
    };

    // Collect custom questions
    form.querySelectorAll('[data-custom-key]').forEach(input => {
      data.custom_answers[input.dataset.customKey] = input.value;
    });

    return data;
  }

  function updateReviewSummary() {
    const data = collectFormData();
    document.getElementById('rev-title').textContent = data.title || '(No title entered)';
    document.getElementById('rev-tagline').textContent = data.tagline || '(No tagline)';
    document.getElementById('rev-desc').textContent = data.description || '(No description)';
    document.getElementById('rev-repo').textContent = data.repo_url || '(None)';
    document.getElementById('rev-live').textContent = data.live_url || '(None)';
  }

  // Navigation handlers
  btnPrev.addEventListener('click', () => {
    if (currentStepIdx > 0) showStep(currentStepIdx - 1);
  });

  btnNext.addEventListener('click', () => {
    if (currentStepIdx < steps.length - 1) showStep(currentStepIdx + 1);
  });

  stepTabs.forEach((tab, i) => {
    tab.addEventListener('click', () => showStep(i));
  });

  // Track unsaved changes
  document.getElementById('submission-form').addEventListener('input', () => {
    isDirty = true;
  });

  window.addEventListener('beforeunload', (e) => {
    if (isDirty) {
      e.preventDefault();
      e.returnValue = 'You have unsaved changes.';
    }
  });

  // Save Draft
  btnSave.addEventListener('click', async () => {
    const payload = collectFormData();
    btnSave.disabled = true;
    btnSave.textContent = 'Saving...';

    try {
      let res;
      if (!projectId) {
        res = await FairPanel.post(`/api/v1/events/${eventId}/projects`, payload);
        projectId = res.id;
        wizard.dataset.projectId = projectId;
      } else {
        res = await FairPanel.patch(`/api/v1/projects/${projectId}`, payload);
      }
      projectVersion = res.version;
      wizard.dataset.projectVersion = projectVersion;
      isDirty = false;
      FairPanel.showToast('Draft saved successfully', 'success');
    } catch (err) {
      if (err.code === 'deadline_passed') {
        FairPanel.showToast('Deadline has passed. Editing is locked.', 'error');
      } else if (err.code === 'version_conflict') {
        FairPanel.showToast('Version conflict: please reload the page to get latest changes.', 'error');
      } else {
        FairPanel.showToast(err.message || 'Failed to save draft', 'error');
      }
    } finally {
      btnSave.disabled = false;
      btnSave.textContent = 'Save Draft';
    }
  });

  // Submit Final Project
  btnSubmit.addEventListener('click', async () => {
    const payload = collectFormData();
    if (!payload.title.trim()) {
      FairPanel.showToast('Please enter a project title before submitting.', 'error');
      showStep(0);
      return;
    }

    if (!confirm('Are you ready to submit your project? You can still make updates before the deadline.')) {
      return;
    }

    btnSubmit.disabled = true;
    btnSubmit.textContent = 'Submitting...';

    try {
      // First ensure draft is saved
      if (!projectId) {
        const createRes = await FairPanel.post(`/api/v1/events/${eventId}/projects`, payload);
        projectId = createRes.id;
        projectVersion = createRes.version;
      } else {
        const patchRes = await FairPanel.patch(`/api/v1/projects/${projectId}`, payload);
        projectVersion = patchRes.version;
      }

      // Then trigger submit endpoint
      const submitRes = await FairPanel.post(`/api/v1/projects/${projectId}/submit`, { version: projectVersion });
      isDirty = false;
      FairPanel.showToast('Project submitted successfully!', 'success');
      setTimeout(() => {
        window.location.href = `/participant/`;
      }, 1000);
    } catch (err) {
      if (err.code === 'deadline_passed') {
        FairPanel.showToast('Submissions are closed. Cannot submit.', 'error');
      } else {
        FairPanel.showToast(err.message || 'Failed to submit project', 'error');
      }
      btnSubmit.disabled = false;
      btnSubmit.textContent = 'Submit Project';
    }
  });

  showStep(0);
});
