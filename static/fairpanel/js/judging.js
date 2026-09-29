/**
 * FairPanel - Judge Review Interface (judging.js)
 * 3-Column layout interactions, criteria scoring, draft saving, submission,
 * and conflict-of-interest reporting.
 */

document.addEventListener('DOMContentLoaded', () => {
  const container = document.querySelector('.judge-review-container');
  if (!container) return;

  const projectId = container.dataset.projectId;
  const assignmentId = container.dataset.assignmentId;
  let reviewVersion = parseInt(container.dataset.reviewVersion || '1', 10);

  const btnSaveDraft = document.getElementById('btn-judge-save-draft');
  const btnSubmitReview = document.getElementById('btn-judge-submit-review');
  const btnConflict = document.getElementById('btn-report-conflict');
  const commentInput = document.getElementById('review-comment');

  // Handle score buttons
  document.querySelectorAll('.rubric-criterion-card').forEach(card => {
    const critKey = card.dataset.criterionKey;
    const scoreBtns = card.querySelectorAll('.score-btn');
    const hiddenInput = card.querySelector(`input[name="score_${critKey}"]`);

    scoreBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        scoreBtns.forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        if (hiddenInput) {
          hiddenInput.value = btn.dataset.score;
        }
      });
    });
  });

  function collectReviewScores() {
    const scores = {};
    document.querySelectorAll('.rubric-criterion-card').forEach(card => {
      const critKey = card.dataset.criterionKey;
      const selected = card.querySelector('.score-btn.selected');
      if (selected) {
        scores[critKey] = parseFloat(selected.dataset.score);
      }
    });
    return scores;
  }

  // Save Review Draft
  if (btnSaveDraft) {
    btnSaveDraft.addEventListener('click', async () => {
      const scores = collectReviewScores();
      const comment = commentInput ? commentInput.value : '';

      btnSaveDraft.disabled = true;
      btnSaveDraft.textContent = 'Saving...';

      try {
        const res = await FairPanel.put(`/api/v1/projects/${projectId}/review`, {
          criteria_scores: scores,
          comment: comment,
          version: reviewVersion
        });
        reviewVersion = res.version;
        FairPanel.showToast('Draft review saved', 'success');
      } catch (err) {
        FairPanel.showToast(err.message || 'Failed to save review draft', 'error');
      } finally {
        btnSaveDraft.disabled = false;
        btnSaveDraft.textContent = 'Save Draft';
      }
    });
  }

  // Submit Final Review
  if (btnSubmitReview) {
    btnSubmitReview.addEventListener('click', async () => {
      const scores = collectReviewScores();
      const comment = commentInput ? commentInput.value : '';

      // Validate all criteria scored
      const totalCriteria = document.querySelectorAll('.rubric-criterion-card').length;
      if (Object.keys(scores).length < totalCriteria) {
        FairPanel.showToast('Please score all criteria before submitting.', 'error');
        return;
      }

      if (!confirm('Are you ready to submit your review score?')) {
        return;
      }

      btnSubmitReview.disabled = true;
      btnSubmitReview.textContent = 'Submitting...';

      try {
        const res = await FairPanel.post(`/api/v1/projects/${projectId}/review/submit`, {
          criteria_scores: scores,
          comment: comment,
          version: reviewVersion
        });
        FairPanel.showToast('Review submitted successfully!', 'success');

        // Check if there is a next project to navigate to
        const nextUrl = container.dataset.nextProjectUrl;
        if (nextUrl) {
          setTimeout(() => {
            window.location.href = nextUrl;
          }, 800);
        } else {
          setTimeout(() => {
            window.location.href = '/judge/';
          }, 1000);
        }
      } catch (err) {
        FairPanel.showToast(err.message || 'Failed to submit review', 'error');
        btnSubmitReview.disabled = false;
        btnSubmitReview.textContent = 'Submit Review';
      }
    });
  }

  // Conflict of Interest
  if (btnConflict && assignmentId) {
    btnConflict.addEventListener('click', async () => {
      const reason = prompt('Please describe your conflict of interest with this project (e.g. mentor, team colleague, personal connection):');
      if (!reason || !reason.trim()) return;

      try {
        await FairPanel.post(`/api/v1/assignments/${assignmentId}/conflict`, { reason: reason.trim() });
        FairPanel.showToast('Conflict recorded. This project has been removed from your active queue.', 'info');
        setTimeout(() => {
          window.location.href = '/judge/';
        }, 1200);
      } catch (err) {
        FairPanel.showToast(err.message || 'Failed to report conflict', 'error');
      }
    });
  }
});
