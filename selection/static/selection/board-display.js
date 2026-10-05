(function () {
    var POLL_INTERVAL = 2000;
    var STATUS_URL = "/board/display/status/";
    var ACTION_URL = "/board/action/";
    var lastVersion = null;
    var polling = false;

    var idleEl = document.getElementById("boardIdle");
    var idleTextEl = document.getElementById("boardIdleText");
    var readyEl = document.getElementById("boardReady");
    var card = document.getElementById("boardCard");
    var nameEl = card.querySelector(".reveal-name");
    var avatarEl = card.querySelector(".avatar-ring");
    var subEl = card.querySelector(".reveal-sub");
    var activeControls = document.getElementById("activeControls");
    var nextControls = document.getElementById("nextControls");
    var questionPanel = document.getElementById("questionPanel");
    var questionTextEl = document.getElementById("questionText");
    var questionImageEl = document.getElementById("questionImage");
    var questionChoicesEl = document.getElementById("questionChoices");
    var questionNumberEl = document.getElementById("questionNumber");
    var numberAnswerInput = document.getElementById("numberAnswerInput");
    var choiceConfirmBar = document.getElementById("choiceConfirmBar");
    var choiceConfirmText = document.getElementById("choiceConfirmText");
    var answerFeedbackEl = document.getElementById("answerFeedback");
    var lastStudentId = null;
    var lastFeedbackShownFor = null;
    var lastQuestionId = null;
    var selectedChoice = null;

    function csrfToken() {
        var input = document.querySelector("input[name=csrfmiddlewaretoken]");
        return input ? input.value : "";
    }

    function postAction(action, extra) {
        var params = new URLSearchParams(Object.assign({ action: action }, extra || {}));
        fetch(ACTION_URL, {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken() },
            body: params,
        }).then(function () {
            poll();
        }).catch(function () {});
    }

    function hideAll() {
        idleEl.style.display = "none";
        readyEl.style.display = "none";
        card.style.display = "none";
        activeControls.style.display = "none";
        nextControls.style.display = "none";
    }

    function showWaiting(state) {
        hideAll();
        lastStudentId = null;
        lastFeedbackShownFor = null;
        lastQuestionId = null;
        idleEl.style.display = "";
        idleTextEl.textContent = state === "attendance"
            ? "Taking attendance…"
            : "Waiting for the teacher to start a class…";
    }

    function showReady() {
        hideAll();
        lastStudentId = null;
        lastFeedbackShownFor = null;
        lastQuestionId = null;
        readyEl.style.display = "";
    }

    function selectChoice(choice) {
        selectedChoice = choice;
        Array.from(questionChoicesEl.children).forEach(function (btn) {
            btn.classList.toggle("selected", btn.textContent === choice);
        });
        choiceConfirmText.textContent = choice;
        choiceConfirmBar.style.display = "";
    }

    function clearChoiceSelection() {
        selectedChoice = null;
        Array.from(questionChoicesEl.children).forEach(function (btn) {
            btn.classList.remove("selected");
        });
        choiceConfirmBar.style.display = "none";
    }

    function renderQuestion(question) {
        questionChoicesEl.innerHTML = "";
        questionNumberEl.classList.add("d-none");
        clearChoiceSelection();

        if (question.image_url) {
            questionImageEl.src = question.image_url;
            questionImageEl.style.display = "";
        } else {
            questionImageEl.style.display = "none";
        }
        questionTextEl.textContent = question.text;

        if (question.answer_type === "multiple_choice") {
            (question.choices || []).forEach(function (choice) {
                var btn = document.createElement("button");
                btn.type = "button";
                btn.className = "btn btn-choice";
                btn.textContent = choice;
                btn.addEventListener("click", function () { selectChoice(choice); });
                questionChoicesEl.appendChild(btn);
            });
        } else if (question.answer_type === "number") {
            questionNumberEl.classList.remove("d-none");
        }
    }

    function renderAnswerFeedback(data) {
        var key = data.student.student_id + ":" + data.outcome;
        var alreadyShown = key === lastFeedbackShownFor;
        lastFeedbackShownFor = key;

        if (data.outcome === "solved") {
            answerFeedbackEl.className = "answer-feedback correct";
            answerFeedbackEl.innerHTML = '<i class="bi bi-check-circle-fill"></i> Correct!'
                + (data.points ? ' +' + data.points + ' point' + (data.points > 1 ? 's' : '') : '');
            if (!alreadyShown) {
                window.BoardReveal.confetti(card, 20);
            }
        } else if (data.outcome === "partial") {
            answerFeedbackEl.className = "answer-feedback neutral";
            answerFeedbackEl.innerHTML = '<i class="bi bi-dash-circle"></i> So close — partly there!';
        } else if (data.outcome) {
            answerFeedbackEl.className = "answer-feedback neutral";
            answerFeedbackEl.innerHTML = '<i class="bi bi-emoji-smile"></i> Good try — we’ll come back to this topic.';
        } else {
            answerFeedbackEl.className = "answer-feedback";
            answerFeedbackEl.innerHTML = "";
        }
    }

    function renderControls(data) {
        if (data.outcome_set) {
            nextControls.style.display = "";
            renderAnswerFeedback(data);
            return;
        }
        activeControls.style.display = "";

        if (data.question) {
            questionPanel.style.display = "";
            if (data.question.id !== lastQuestionId) {
                lastQuestionId = data.question.id;
                renderQuestion(data.question);
            }
        } else {
            questionPanel.style.display = "none";
            lastQuestionId = null;
        }
    }

    function showCard(data) {
        var student = data.student;
        var isNewStudent = student.student_id !== lastStudentId;

        hideAll();
        card.style.display = "";

        if (isNewStudent) {
            avatarEl.innerHTML = student.photo_url
                ? '<img src="' + student.photo_url + '" alt="' + student.name + '">'
                : student.name.charAt(0);
            subEl.textContent = student.student_id + " · " + student.classroom;
            nameEl.setAttribute("data-final-name", student.name);
            card.setAttribute("data-candidates", (data.candidate_names || []).join("|"));
            lastStudentId = student.student_id;
        } else {
            nameEl.textContent = student.name;
            card.classList.add("pop");
        }

        renderControls(data);

        if (isNewStudent) {
            window.BoardReveal.run(card);
        }
    }

    function poll() {
        if (polling) {
            return;
        }
        polling = true;

        fetch(STATUS_URL)
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (!data.active) {
                    lastVersion = data.version;
                    showWaiting("idle");
                    return;
                }
                if (data.state === "attendance") {
                    lastVersion = data.version;
                    showWaiting("attendance");
                    return;
                }
                if (!data.student) {
                    lastVersion = data.version;
                    showReady();
                    return;
                }
                if (data.version !== lastVersion) {
                    lastVersion = data.version;
                    showCard(data);
                }
            })
            .catch(function () {})
            .then(function () { polling = false; });
    }

    document.getElementById("callBtn").addEventListener("click", function () { postAction("call"); });
    document.getElementById("callAgainBtn").addEventListener("click", function () { postAction("call"); });
    document.getElementById("skipAbsentBtn").addEventListener("click", function () { postAction("skip", { reason: "absent" }); });
    document.getElementById("skipNotReadyBtn").addEventListener("click", function () { postAction("skip", { reason: "not_ready" }); });
    document.getElementById("skipOtherBtn").addEventListener("click", function () { postAction("skip", { reason: "other" }); });
    document.getElementById("choiceConfirmYes").addEventListener("click", function () {
        if (selectedChoice !== null) {
            postAction("answer_question", { choice: selectedChoice });
            selectedChoice = null;
        }
    });
    document.getElementById("choiceConfirmNo").addEventListener("click", clearChoiceSelection);
    document.getElementById("numberSubmitBtn").addEventListener("click", function () {
        if (numberAnswerInput.value !== "") {
            postAction("answer_question", { number_answer: numberAnswerInput.value });
            numberAnswerInput.value = "";
        }
    });

    poll();
    setInterval(poll, POLL_INTERVAL);
})();
