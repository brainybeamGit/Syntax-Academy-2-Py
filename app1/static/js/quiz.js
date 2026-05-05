let current = 0;
const questions = document.querySelectorAll(".question-box");
const total = questions.length;

const nextBtn = document.getElementById("nextBtn");
const prevBtn = document.getElementById("prevBtn");
const submitBtn = document.getElementById("submitBtn");
const qnum = document.getElementById("qnum");

if (total > 0) {

    questions[0].classList.add("active");
    updateButtons();

    function showQuestion(index) {
        questions[current].classList.remove("active");
        current = index;
        questions[current].classList.add("active");
        qnum.innerText = current + 1;
        updateButtons();
    }

    nextBtn.onclick = () => {
        if (current < total - 1) showQuestion(current + 1);
    };

    prevBtn.onclick = () => {
        if (current > 0) showQuestion(current - 1);
    };

    function updateButtons() {

        if (current === 0)
            prevBtn.style.display = "none";
        else
            prevBtn.style.display = "inline-block";

        if (current === total - 1) {
            nextBtn.style.display = "none";
            submitBtn.style.display = "inline-block";
        } else {
            nextBtn.style.display = "inline-block";
            submitBtn.style.display = "none";
        }
    }

    // SUBMIT QUIZ
        document.getElementById("quizForm").onsubmit = async function(e){
        e.preventDefault();

        const formData = new FormData(this);

        const response = await fetch(`/submit_quiz/${QUIZ_ID}/`, {
            method: "POST",
            headers: {
                "X-CSRFToken": CSRF_TOKEN
            },
            body: formData
        });

        const data = await response.json();

        document.querySelector(".quiz-container").innerHTML = `
            <div class="result-box">
                <h2>🎉 Quiz Completed</h2>
                <h3>Your Score: ${data.score} / ${data.total}</h3>

                <a href="/courses/${COURSE_ID}/" class="return-btn">
                    ⬅ Back to Course
                </a>
            </div>
        `;

    };
}
