const video = document.getElementById("mainVideo");
const videoTitle = document.getElementById("videoTitle");
const placeholder = document.getElementById("videoPlaceholder");
const videoPlayerShell = document.getElementById("videoPlayerShell");
const backward10Btn = document.getElementById("backward10Btn");
const forward10Btn = document.getElementById("forward10Btn");
const lessonItems = document.querySelectorAll(".lesson-item");
const quizAccessTrigger = document.getElementById("quizAccessTrigger");
const LESSON_COMPLETION_THRESHOLD = 0.95;
const completionSyncInFlight = new Set();
let activeLessonId = null;
let progressSaveTimeout = null;
let isSwitchingLesson = false;

function readSavedProgress() {
    try {
        const saved = localStorage.getItem(PLAYER_STORAGE_KEY);
        if (!saved) return null;

        const parsed = JSON.parse(saved);

        if (parsed.lessonId) {
            return {
                lastLessonId: parsed.lessonId,
                lessons: {
                    [parsed.lessonId]: {
                        currentTime: parsed.currentTime || 0,
                        title: parsed.title || "",
                        updatedAt: parsed.updatedAt || Date.now(),
                        isCompleted: Boolean(parsed.isCompleted),
                        serverSynced: Boolean(parsed.serverSynced)
                    }
                }
            };
        }

        return {
            lastLessonId: parsed.lastLessonId || null,
            lessons: parsed.lessons || {}
        };
    } catch (error) {
        return null;
    }
}

function writeSavedProgress(progress) {
    try {
        localStorage.setItem(PLAYER_STORAGE_KEY, JSON.stringify(progress));
    } catch (error) {
        // Keep playback working even if storage is unavailable.
    }
}

function clearSavedProgress() {
    try {
        localStorage.removeItem(PLAYER_STORAGE_KEY);
    } catch (error) {
        // Keep playback working even if storage is unavailable.
    }
}

function getLessonElement(lessonId) {
    return document.querySelector(`.lesson-item[data-lesson-id="${lessonId}"]`);
}

function getRemainingLessonsLabel(remainingLessons) {
    return `${remainingLessons} lesson${remainingLessons === 1 ? "" : "s"} remaining`;
}

function getLessonCompletionSnapshot() {
    const playableLessonItems = Array.from(lessonItems).filter((item) => item.dataset.lessonId);
    const totalLessons = playableLessonItems.length;
    const completedLessons = playableLessonItems.filter((item) => item.classList.contains("is-completed")).length;
    const remainingLessons = Math.max(totalLessons - completedLessons, 0);

    return {
        totalLessons,
        completedLessons,
        remainingLessons,
        allCompleted: totalLessons > 0 && completedLessons === totalLessons
    };
}

function updateQuizAccessState(isReady, remainingLessons) {
    if (!quizAccessTrigger) return;

    const enrolled = quizAccessTrigger.dataset.enrolled === "True";
    const quizStateLabel = quizAccessTrigger.querySelector(".quiz-action-label");
    const lockIcon = quizAccessTrigger.querySelector(".lock-icon");

    quizAccessTrigger.dataset.quizReady = String(Boolean(isReady));
    quizAccessTrigger.dataset.remainingLessons = String(remainingLessons || 0);
    quizAccessTrigger.classList.toggle("locked", !enrolled || !isReady);

    if (quizStateLabel) {
        if (!enrolled) {
            quizStateLabel.innerText = "Quiz Locked";
        } else if (isReady) {
            quizStateLabel.innerText = "Attempt Quiz";
        } else {
            quizStateLabel.innerText = `${remainingLessons || 0} left`;
        }
    }

    if (enrolled && isReady && lockIcon) {
        lockIcon.remove();
    }
}

function refreshQuizAccessFromLessonTicks() {
    if (!quizAccessTrigger) return;

    const enrolled = quizAccessTrigger.dataset.enrolled === "True";

    if (!enrolled) {
        updateQuizAccessState(false, Number(quizAccessTrigger.dataset.remainingLessons || 0));
        return;
    }

    const completion = getLessonCompletionSnapshot();

    if (completion.allCompleted) {
        updateQuizAccessState(true, 0);
        return;
    }

    updateQuizAccessState(false, completion.remainingLessons);
}

function updateLessonCompletionUI(lessonId, isCompleted) {
    const lessonElement = getLessonElement(lessonId);

    if (!lessonElement) return;

    lessonElement.classList.toggle("is-completed", Boolean(isCompleted));
    refreshQuizAccessFromLessonTicks();
}

function syncCompletedLessonsUI() {
    const savedProgress = readSavedProgress();

    lessonItems.forEach((item) => {
        const lessonProgress = savedProgress && savedProgress.lessons
            ? savedProgress.lessons[item.dataset.lessonId]
            : null;

        updateLessonCompletionUI(item.dataset.lessonId, lessonProgress && lessonProgress.isCompleted);
    });
}

function mergeServerCompletedLessons() {
    if (!Array.isArray(COMPLETED_LESSON_IDS) || !COMPLETED_LESSON_IDS.length) return;

    const savedProgress = readSavedProgress() || { lastLessonId: null, lessons: {} };
    let hasChanges = false;

    COMPLETED_LESSON_IDS.forEach((lessonId) => {
        const lessonKey = String(lessonId);
        const existingLessonProgress = savedProgress.lessons[lessonKey] || {};

        if (!existingLessonProgress.isCompleted || !existingLessonProgress.serverSynced) {
            savedProgress.lessons[lessonKey] = {
                ...existingLessonProgress,
                currentTime: Number(existingLessonProgress.currentTime || 0),
                title: existingLessonProgress.title || "",
                updatedAt: existingLessonProgress.updatedAt || Date.now(),
                isCompleted: true,
                serverSynced: true
            };
            hasChanges = true;
        }
    });

    if (hasChanges) {
        writeSavedProgress(savedProgress);
    }
}

function syncLessonCompletionToServer(lessonId) {
    const lessonKey = String(lessonId);
    const lessonElement = getLessonElement(lessonKey);

    if (!lessonElement || completionSyncInFlight.has(lessonKey)) return;

    const completeUrl = lessonElement.dataset.completeUrl;

    if (!completeUrl) return;

    completionSyncInFlight.add(lessonKey);

    fetch(completeUrl, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCookie("csrftoken")
        }
    })
        .then((response) => {
            if (!response.ok) {
                throw new Error("Unable to sync lesson completion.");
            }

            return response.json();
        })
        .then((data) => {
            const savedProgress = readSavedProgress() || { lastLessonId: null, lessons: {} };
            const existingLessonProgress = savedProgress.lessons[lessonKey] || {};

            savedProgress.lessons[lessonKey] = {
                ...existingLessonProgress,
                currentTime: Number(existingLessonProgress.currentTime || 0),
                title: existingLessonProgress.title || lessonElement.dataset.title || "",
                updatedAt: Date.now(),
                isCompleted: true,
                serverSynced: true
            };

            writeSavedProgress(savedProgress);
            updateLessonCompletionUI(lessonKey, true);
            updateQuizAccessState(data.all_lessons_completed, Number(data.remaining_lessons || 0));
        })
        .catch(() => {
            // Keep playback working even if completion sync fails temporarily.
        })
        .finally(() => {
            completionSyncInFlight.delete(lessonKey);
        });
}

function syncUnsyncedCompletedLessons() {
    const savedProgress = readSavedProgress();

    if (!savedProgress || !savedProgress.lessons) return;

    Object.entries(savedProgress.lessons).forEach(([lessonId, lessonProgress]) => {
        if (lessonProgress && lessonProgress.isCompleted && !lessonProgress.serverSynced) {
            syncLessonCompletionToServer(lessonId);
        }
    });
}

function hasReachedCompletionThreshold(currentTime) {
    if (!video || !Number.isFinite(video.duration) || video.duration <= 0) return false;

    return (currentTime / video.duration) >= LESSON_COMPLETION_THRESHOLD;
}

function saveVideoProgress(forceTime) {
    if (!video || !activeLessonId || !video.src) return;

    const currentTime = typeof forceTime === "number" ? forceTime : (video.currentTime || 0);
    const savedProgress = readSavedProgress() || { lastLessonId: null, lessons: {} };
    const existingLessonProgress = savedProgress.lessons[activeLessonId] || {};
    const completionCheckTime = Number.isFinite(video.currentTime) ? video.currentTime : currentTime;
    const isCompleted = Boolean(
        existingLessonProgress.isCompleted || hasReachedCompletionThreshold(completionCheckTime)
    );

    savedProgress.lastLessonId = activeLessonId;
    savedProgress.lessons[activeLessonId] = {
        ...existingLessonProgress,
        currentTime: currentTime,
        title: videoTitle.innerText || "",
        updatedAt: Date.now(),
        isCompleted: isCompleted
    };

    writeSavedProgress(savedProgress);
    updateLessonCompletionUI(activeLessonId, isCompleted);

    if (isCompleted && !existingLessonProgress.serverSynced) {
        syncLessonCompletionToServer(activeLessonId);
    }
}

function queueVideoProgressSave() {
    if (progressSaveTimeout) return;

    progressSaveTimeout = window.setTimeout(() => {
        saveVideoProgress();
        progressSaveTimeout = null;
    }, 700);
}

function showLockedPlaceholder() {
    if (videoPlayerShell) {
        videoPlayerShell.style.display = "none";
    }
    video.pause();
    videoTitle.style.display = "none";

    placeholder.style.display = "flex";
    placeholder.innerHTML = `
        <i class="bi bi-lock-fill"></i>
        <h4>Course Locked</h4>
        <p>Please enroll to unlock all lessons and start learning.</p>
    `;
}

function loadLesson(item, options = {}) {
    const enrolled = item.dataset.enrolled === "True";

    if (!enrolled) {
        showLockedPlaceholder();
        return;
    }

    const src = item.dataset.video;
    const title = item.dataset.title;
    const lessonId = item.dataset.lessonId;

    if (!src || !lessonId) return;

    const resumeTime = Number(options.resumeTime || 0);
    const shouldAutoplay = options.autoplay !== false;
    const sourceChanged = video.dataset.lessonId !== lessonId;

    if (sourceChanged && activeLessonId && video.src) {
        saveVideoProgress();
        isSwitchingLesson = true;
        video.pause();
    }

    lessonItems.forEach(el => el.classList.remove("active"));
    item.classList.add("active");

    activeLessonId = lessonId;
    placeholder.style.display = "none";
    if (videoPlayerShell) {
        videoPlayerShell.style.display = "block";
    }
    videoTitle.style.display = "block";
    videoTitle.innerText = title;

    const applyResume = () => {
        isSwitchingLesson = false;

        if (resumeTime > 0 && Number.isFinite(video.duration) && video.duration > 0) {
            video.currentTime = Math.min(resumeTime, Math.max(video.duration - 1, 0));
        }

        if (shouldAutoplay) {
            video.play().catch(() => {});
        }
    };

    if (sourceChanged) {
        video.dataset.lessonId = lessonId;
        video.src = src;
        video.load();
        video.addEventListener("loadedmetadata", applyResume, { once: true });
    } else {
        applyResume();
    }
}

// ===============================
// LESSON CLICK + LOCK SYSTEM
// ===============================

document.querySelectorAll(".lesson-item-legacy-disabled").forEach(item => {

    item.addEventListener("click", function(){

        const enrolled = this.dataset.enrolled === "True";

        const video = document.getElementById("mainVideo");
        const placeholder = document.getElementById("videoPlaceholder");
        const videoTitle = document.getElementById("videoTitle");

        // 🔒 NOT ENROLLED
        if(!enrolled){

            video.style.display = "none";
            video.pause();

            videoTitle.style.display = "none";

            placeholder.style.display = "flex";
            placeholder.innerHTML = `
                <i class="bi bi-lock-fill"></i>
                <h4>Course Locked</h4>
                <p>Please enroll to unlock all lessons and start learning.</p>
            `;

            return;
        }

        // ✅ ENROLLED → PLAY VIDEO
        const src = this.dataset.video;
        const title = this.dataset.title;

        if (!src) return;

        document.querySelectorAll(".lesson-item")
            .forEach(el => el.classList.remove("active"));

        this.classList.add("active");

        placeholder.style.display = "none";

        video.style.display = "block";
        videoTitle.style.display = "block";

        video.pause();
        video.src = src;
        video.load();
        video.play();

        videoTitle.innerText = title;

    });

});

lessonItems.forEach(item => {

    item.addEventListener("click", function(){
        const saved = readSavedProgress();
        const lessonProgress = saved && saved.lessons
            ? saved.lessons[this.dataset.lessonId]
            : null;
        const resumeTime = lessonProgress
            ? Number(lessonProgress.currentTime || 0)
            : 0;

        loadLesson(this, { autoplay: true, resumeTime });
    });

});

if (video) {
    video.addEventListener("timeupdate", queueVideoProgressSave);
    video.addEventListener("pause", () => {
        if (!isSwitchingLesson) {
            saveVideoProgress();
        }
    });
    video.addEventListener("seeked", () => saveVideoProgress());
    video.addEventListener("ended", () => saveVideoProgress(0));

    window.addEventListener("beforeunload", () => saveVideoProgress());
}

if (backward10Btn) {
    backward10Btn.addEventListener("click", function() {
        if (!video || (videoPlayerShell && videoPlayerShell.style.display === "none")) return;
        video.currentTime = Math.max((video.currentTime || 0) - 10, 0);
        saveVideoProgress();
    });
}

if (forward10Btn) {
    forward10Btn.addEventListener("click", function() {
        if (!video || (videoPlayerShell && videoPlayerShell.style.display === "none")) return;
        const duration = Number.isFinite(video.duration) ? video.duration : null;
        const nextTime = (video.currentTime || 0) + 10;
        video.currentTime = duration ? Math.min(nextTime, duration) : nextTime;
        saveVideoProgress();
    });
}

document.addEventListener("DOMContentLoaded", function(){
    mergeServerCompletedLessons();
    syncCompletedLessonsUI();
    syncUnsyncedCompletedLessons();
    refreshQuizAccessFromLessonTicks();

    const saved = readSavedProgress();

    if (!saved || !saved.lastLessonId) return;

    const savedLesson = document.querySelector(`.lesson-item[data-lesson-id="${saved.lastLessonId}"]`);

    if (!savedLesson) {
        clearSavedProgress();
        return;
    }

    const lessonProgress = saved.lessons && saved.lessons[saved.lastLessonId]
        ? saved.lessons[saved.lastLessonId]
        : null;

    loadLesson(savedLesson, {
        autoplay: false,
        resumeTime: Number(lessonProgress ? lessonProgress.currentTime || 0 : 0)
    });
});

/* Toggle dropdown */
function toggleDropdown(id){
    const el = document.getElementById(id);
    el.style.display = el.style.display === "block" ? "none" : "block";
}



function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function postComment() {
    const textBox = document.getElementById("commentText");
    const text = textBox.value.trim();

    if (!text) return;

    fetch(ADD_COMMENT_URL, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body: `course_id=${COURSE_ID}&text=${encodeURIComponent(text)}`
    })
    .then(res => res.json())
    .then(data => {
        const commentList = document.getElementById("commentList");

        if (commentList.innerText.includes("No comments")) {
            commentList.innerHTML = "";
        }

        const div = document.createElement("div");
        div.className = "comment-item";

        div.innerHTML = `
            <div class="comment-header">
                <strong>You</strong>
                <small>${data.created_at}</small>
            </div>
            <p class="comment-text">${data.text}</p>
        `;

        commentList.prepend(div);
        textBox.value = "";
    });
}


function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(
                    cookie.substring(name.length + 1)
                );
                break;
            }
        }
    }
    return cookieValue;
}


function toggleReplies(commentId) {
    const replies = document.getElementById(`replies${commentId}`);
    replies.style.display =
        replies.style.display === "none" ? "block" : "none";
}

function toggleReplyBox(commentId) {
    const box = document.getElementById(`replyBox${commentId}`);
    box.style.display =
        box.style.display === "none" ? "flex" : "none";
}

function replyComment(commentId) {
    const textBox = document.getElementById(`replyText${commentId}`);
    const text = textBox.value.trim();

    if (!text) return;

    fetch("/reply_comment/", {
        method: "POST",
        headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body: `comment_id=${commentId}&text=${encodeURIComponent(text)}`
    })
    .then(res => res.json())
    .then(data => {
        location.reload();
    });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(
                    cookie.substring(name.length + 1)
                );
                break;
            }
        }
    }
    return cookieValue;
}


document.querySelectorAll(".dropdown-item[data-file]").forEach(item => {

    item.addEventListener("click", function(){

        let fileUrl = this.getAttribute("data-file");

        // show viewer
        document.getElementById("pdfViewer").style.display = "block";

        // preview inside iframe
        document.getElementById("pdfFrame").src = fileUrl;

        // download button
        document.getElementById("downloadBtn").href = fileUrl;

        // title
        document.getElementById("pdfTitle").innerText = this.innerText;

        // scroll to viewer
        document.getElementById("pdfViewer").scrollIntoView({behavior:"smooth"});

    });

});


let selectedStars = 0;

const stars = document.querySelectorAll('.star');

stars.forEach((star, index) => {

    star.addEventListener('click', () => {
        selectedStars = index + 1;
        updateStars();
        document.getElementById("selectedStarsInput").value = selectedStars;
    });

    star.addEventListener('mouseenter', () => {
        highlightStars(index + 1);
    });

    star.addEventListener('mouseleave', () => {
        updateStars();
    });

});

function highlightStars(count){
    stars.forEach((star, i) => {
        star.classList.toggle('active', i < count);
    });
}

function updateStars(){
    highlightStars(selectedStars);
}


// 📨 Submit review
let reviewForm = document.getElementById("reviewForm");

if(reviewForm){

reviewForm.addEventListener("submit", function(e){

    e.preventDefault();

    let formData = new FormData(reviewForm);

    fetch(SUBMIT_REVIEW_URL,{
        method:"POST",
        headers:{
            "X-CSRFToken": getCookie("csrftoken")
        },
        body: formData
    })
    .then(res=>res.json())
    .then(data=>{

        if(data.status === "created"){
            showMessage("🎉 Thank you for your review!");
        }

        if(data.status === "updated"){
            showMessage("✏️ Review updated successfully!");
        }

    });

});

}

function showMessage(msg){

    let container = document.querySelector(".review-minimal");

    let message = document.createElement("div");
    message.innerText = msg;
    message.style.color = "#6cf2c2";
    message.style.marginTop = "15px";
    message.style.fontWeight = "500";

    container.appendChild(message);

}



// ===============================
// ENROLLMENT + RAZORPAY PAYMENT
// ===============================

document.addEventListener("DOMContentLoaded", function(){

const enrollBtn = document.getElementById("enrollBtn");

if(!enrollBtn) return;

// If already enrolled → disable button
if(enrollBtn.innerText.includes("Enrolled")){
    enrollBtn.disabled = true;
    enrollBtn.classList.remove("enroll-btn");
    enrollBtn.classList.add("enrolled-btn");
    return;
}

enrollBtn.addEventListener("click", function(){

    fetch(ENROLL_URL)
    .then(res => res.json())
    .then(data => {

        // Login required
        if(data.status === "login_required"){
            window.location.href = "/login/";
            return;
        }

        // Payment required
        if(data.status === "payment_required"){

            var options = {

                key: data.key,
                amount: data.amount,
                currency: "INR",
                name: "Syntax Academy",
                description: data.course_name,
                order_id: data.order_id,

                handler: function (response){
                    const payload = new URLSearchParams({
                        course_id: String(data.course_id),
                        payment_id: response.razorpay_payment_id || "",
                        order_id: response.razorpay_order_id || "",
                        signature: response.razorpay_signature || ""
                    });

                    // Save enrollment after payment
                    fetch("/payment-success/",{
                        method:"POST",
                        headers:{
                            "Content-Type":"application/x-www-form-urlencoded",
                            "X-CSRFToken": getCookie("csrftoken")
                        },
                        body: payload.toString()
                    })
                    .then(res => res.json())
                    .then(resData => {

                        if(resData.status === "enrolled"){

                            // Update button
                            enrollBtn.innerText = "✔ Enrolled";
                            enrollBtn.disabled = true;

                            enrollBtn.classList.remove("enroll-btn");
                            enrollBtn.classList.add("enrolled-btn");

                            // Reload page so lessons unlock
                            setTimeout(()=>{
                                window.location.reload();
                            },700);

                        } else {
                            alert(resData.message || "Payment verification failed.");
                        }

                    });

                },

                theme:{
                    color:"#6cf2c2"
                }

            };

            var rzp = new Razorpay(options);
            rzp.open();
            return;

        }

        // If enrollment removed
        if(data.status === "removed"){
            location.reload();
            return;
        }

        alert(data.message || "Unable to start payment right now.");

    });

});

});


// ===============================
// CSRF HELPER
// ===============================

function getCookie(name){

let cookieValue = null;

if(document.cookie && document.cookie !== ""){

const cookies = document.cookie.split(";");

for(let i=0;i<cookies.length;i++){

const cookie = cookies[i].trim();

if(cookie.substring(0,name.length+1) === (name + "=")){

cookieValue = decodeURIComponent(cookie.substring(name.length+1));
break;

}

}

}

return cookieValue;

}



// ===============================
// NOTES LOCK SYSTEM
// ===============================

document.querySelectorAll(".note-row").forEach(item => {

    item.addEventListener("click", function(e){

        const enrolled = this.dataset.enrolled === "True";

        if(!enrolled){
            e.preventDefault();
            alert("🔒 Please enroll in this course to access notes.");
            return;
        }

    });

});


// ===============================
// QUIZ LOCK SYSTEM
// ===============================

document.querySelectorAll(".quiz-item").forEach(item => {

    item.addEventListener("click", function(){

        const enrolled = this.dataset.enrolled === "True";

        if(!enrolled){
            alert("🔒 Please enroll in this course to unlock the quiz.");
            return;
        }

    });

});

if(quizAccessTrigger){
    quizAccessTrigger.addEventListener("click", function(){
        const enrolled = this.dataset.enrolled === "True";
        const completion = getLessonCompletionSnapshot();
        const quizReady = completion.allCompleted || this.dataset.quizReady === "True";
        const remainingLessons = quizReady
            ? 0
            : completion.totalLessons
                ? completion.remainingLessons
                : Number(this.dataset.remainingLessons || 0);
        const quizUrl = this.dataset.quizUrl;

        if(!enrolled){
            return;
        }

        if(!quizReady){
            alert(`Complete all lessons before attempting the quiz. ${getRemainingLessonsLabel(remainingLessons)}.`);
            return;
        }

        updateQuizAccessState(true, 0);

        if(quizUrl){
            window.location.href = quizUrl;
        }
    });
}
