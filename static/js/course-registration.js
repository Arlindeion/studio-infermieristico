document.addEventListener('DOMContentLoaded', function() {
    const dateSelect = document.querySelector('[data-course-date-select]');
    const locationOutput = document.querySelector('[data-course-location-output]');

    if (!dateSelect || !locationOutput) return;

    function updateCourseLocation() {
        const selectedOption = dateSelect.selectedOptions[0];
        locationOutput.value = selectedOption ? selectedOption.dataset.courseLocation || '' : '';
    }

    dateSelect.addEventListener('change', updateCourseLocation);
    updateCourseLocation();
});
