/**
 * FairPanel - Organizer Operations (organizer.js)
 * Balanced judge assignments, eligibility decision modals with reasons,
 * and frozen publication workflows.
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Run Balanced Assignment
  const btnRunBalanced = document.getElementById('btn-run-balanced-assignment');
  if (btnRunBalanced) {
    btnRunBalanced.addEventListener('click', async () => {
      const eventId = btnRunBalanced.dataset.eventId;
      const reviewsPerProject = parseInt(document.getElementById('input-reviews-per-project')?.value || '3', 10);

      if (!confirm(`Run balanced round-robin assignment targeting ${reviewsPerProject} reviews per project? Existing completed reviews will be preserved.`)) {
        return;
      }

      btnRunBalanced.disabled = true;
      btnRunBalanced.textContent = 'Assigning...';

      try {
        const res = await FairPanel.post(`/api/v1/events/${eventId}/assignments`, {
          strategy: 'balanced',
          reviews_per_project: reviewsPerProject
        });
        FairPanel.showToast(res.message || `Created ${res.created_count} assignments`, 'success');
        setTimeout(() => location.reload(), 1200);
      } catch (err) {
        FairPanel.showToast(err.message || 'Failed to run assignment', 'error');
        btnRunBalanced.disabled = false;
        btnRunBalanced.textContent = 'Run Balanced Assignment';
      }
    });
  }

  // 2. Project Eligibility Update
  document.querySelectorAll('.btn-update-eligibility').forEach(btn => {
    btn.addEventListener('click', async () => {
      const projectId = btn.dataset.projectId;
      const currentEligibility = btn.dataset.currentEligibility;
      const newEligibility = currentEligibility === 'eligible' ? 'ineligible' : 'eligible';

      let reason = '';
      if (newEligibility === 'ineligible') {
        reason = prompt('Reason for marking project ineligible (required for audit):');
        if (!reason || !reason.trim()) {
          FairPanel.showToast('Reason is required to exclude a project.', 'error');
          return;
        }
      } else {
        reason = prompt('Reason for restoring project eligibility:') || 'Restored by organizer';
      }

      try {
        await FairPanel.patch(`/api/v1/projects/${projectId}/eligibility`, {
          eligibility: newEligibility,
          reason: reason.trim()
        });
        FairPanel.showToast(`Project marked as ${newEligibility}`, 'success');
        setTimeout(() => location.reload(), 800);
      } catch (err) {
        FairPanel.showToast(err.message || 'Failed to update eligibility', 'error');
      }
    });
  });

  // 3. Publish Results Snapshot
  const btnPublishResults = document.getElementById('btn-publish-results');
  if (btnPublishResults) {
    btnPublishResults.addEventListener('click', async () => {
      const eventId = btnPublishResults.dataset.eventId;
      const previewVersion = btnPublishResults.dataset.previewVersion;
      const rankingMethod = document.querySelector('input[name="ranking_method"]:checked')?.value || 'raw';
      const reason = document.getElementById('publish-reason')?.value || 'Official results publication';

      if (!confirm(`Are you sure you want to publish the official results using "${rankingMethod.toUpperCase()}" ranking method? This creates an immutable snapshot.`)) {
        return;
      }

      btnPublishResults.disabled = true;
      btnPublishResults.textContent = 'Publishing...';

      try {
        const res = await FairPanel.post(`/api/v1/events/${eventId}/results/publish`, {
          ranking_method: rankingMethod,
          preview_version: previewVersion,
          reason: reason,
          acknowledged_warnings: []
        });
        FairPanel.showToast('Results published successfully!', 'success');
        setTimeout(() => location.reload(), 1000);
      } catch (err) {
        FairPanel.showToast(err.message || 'Failed to publish results', 'error');
        btnPublishResults.disabled = false;
        btnPublishResults.textContent = 'Publish Results Snapshot';
      }
    });
  }
});
