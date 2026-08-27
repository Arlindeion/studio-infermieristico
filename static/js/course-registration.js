document.addEventListener('DOMContentLoaded', function() {
    const dateSelect = document.querySelector('[data-course-date-select]');
    const locationOutput = document.querySelector('[data-course-location-output]');
    const courseForm = document.querySelector('[data-course-registration-form]');
    const participationSelect = document.getElementById('partecipazione');
    const secondParticipantFields = document.querySelector('[data-second-participant-fields]');
    const serverError = document.querySelector('[data-course-form-error]');

    if (dateSelect && locationOutput) {
        function updateCourseLocation() {
            const selectedOption = dateSelect.selectedOptions[0];
            locationOutput.value = selectedOption ? selectedOption.dataset.courseLocation || '' : '';
        }

        dateSelect.addEventListener('change', updateCourseLocation);
        updateCourseLocation();
    }

    function setFieldError(field, message = '') {
        if (!field) return null;
        const group = field.closest('.form-gruppo') || field;
        group.classList.add('is-field-error');
        field.setAttribute('aria-invalid', 'true');
        let inlineMessage = group.querySelector('.field-error-message');
        if (message) {
            if (!inlineMessage) {
                inlineMessage = document.createElement('span');
                inlineMessage.className = 'field-error-message';
                inlineMessage.id = `${field.id || field.name}-field-error`;
                group.appendChild(inlineMessage);
            }
            inlineMessage.textContent = message;
            field.setAttribute('aria-describedby', inlineMessage.id);
        }
        return group;
    }

    function clearFieldError(field) {
        if (!field) return;
        const group = field.closest('.form-gruppo') || field;
        group.classList.remove('is-field-error');
        field.removeAttribute('aria-invalid');
        const inlineMessage = group.querySelector('.field-error-message');
        if (inlineMessage && field.getAttribute('aria-describedby') === inlineMessage.id) {
            field.removeAttribute('aria-describedby');
        }
        if (inlineMessage) inlineMessage.remove();
    }

    if (participationSelect && secondParticipantFields) {
        const secondParticipantName = secondParticipantFields.querySelector('[name="nome_secondo_partecipante"]');
        const secondParticipantTaxCode = secondParticipantFields.querySelector('[name="codice_fiscale_secondo_partecipante"]');

        function updateSecondParticipantFields() {
            const isCouple = participationSelect.value.toLowerCase().startsWith('coppia');
            secondParticipantFields.hidden = !isCouple;
            secondParticipantName.disabled = !isCouple;
            secondParticipantName.required = isCouple;
            secondParticipantTaxCode.disabled = !isCouple;
            if (!isCouple) {
                clearFieldError(secondParticipantName);
                clearFieldError(secondParticipantTaxCode);
            }
        }

        participationSelect.addEventListener('change', updateSecondParticipantFields);
        updateSecondParticipantFields();
    }

    if (!courseForm) return;

    courseForm.addEventListener('invalid', function(event) {
        const field = event.target;
        const group = setFieldError(field, field.validationMessage);
        window.requestAnimationFrame(function() {
            group.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'auto'});
            field.focus({preventScroll: true});
        });
    }, true);

    courseForm.addEventListener('input', function(event) {
        if (event.target.checkValidity()) clearFieldError(event.target);
    });
    courseForm.addEventListener('change', function(event) {
        if (event.target.checkValidity()) clearFieldError(event.target);
    });

    if (serverError) {
        const fieldName = serverError.dataset.errorField;
        const invalidField = fieldName
            ? courseForm.querySelector(`[name="${CSS.escape(fieldName)}"]`)
            : null;
        const errorMessage = serverError.querySelector('span')?.textContent.trim() || '';
        const scrollTarget = setFieldError(invalidField, errorMessage) || serverError;
        window.requestAnimationFrame(function() {
            scrollTarget.scrollIntoView({block: 'center', inline: 'nearest', behavior: 'auto'});
            (invalidField || serverError).focus({preventScroll: true});
        });
    }
});
