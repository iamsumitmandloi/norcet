const DATA_PATH = "../structured_json/final_questions.json";
const FALLBACK_PATH = "../structured_json/tagged_questions.json";

const state = {
  questions: [],
  filtered: [],
  selectedYear: "",
  selectedSubject: "",
  selectedTopic: "",
};

const yearSelect = document.getElementById("yearSelect");
const subjectSelect = document.getElementById("subjectSelect");
const topicSelect = document.getElementById("topicSelect");
const questionList = document.getElementById("questionList");
const countEl = document.getElementById("count");
const year2022Actions = document.getElementById("year2022Actions");
const viewPdfBtn = document.getElementById("viewPdfBtn");
const startTestBtn = document.getElementById("startTestBtn");
const downloadPdfBtn = document.getElementById("downloadPdfBtn");
const pdfPanel = document.getElementById("pdfPanel");
const pdfFrame = document.getElementById("pdfFrame");

async function loadData() {
  for (const path of [DATA_PATH, FALLBACK_PATH]) {
    try {
      const res = await fetch(path);
      if (!res.ok) continue;
      const data = await res.json();
      const questions = data.questions || data.records || [];
      if (questions.length > 0) return questions;
    } catch (e) {
      console.warn(`Unable to load ${path}`, e);
    }
  }
  return [];
}

function uniqueSorted(values) {
  return [...new Set(values)].sort((a, b) => String(a).localeCompare(String(b)));
}

function fillSelect(selectEl, values, allLabel) {
  const current = selectEl.value;
  selectEl.innerHTML = "";
  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = allLabel;
  selectEl.appendChild(allOption);

  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    selectEl.appendChild(option);
  });

  if ([...selectEl.options].some((o) => o.value === current)) {
    selectEl.value = current;
  }
}

function updateYearControls() {
  if (state.selectedYear === "2022") {
    year2022Actions.classList.remove("hidden");
    const pdfPath = "../raw_pdfs/2022/norcet_2022.pdf";
    downloadPdfBtn.href = pdfPath;
    pdfFrame.src = pdfPath;
  } else {
    year2022Actions.classList.add("hidden");
    pdfPanel.classList.add("hidden");
  }
}

function applyFilters() {
  state.filtered = state.questions.filter((q) => {
    const yearPass = !state.selectedYear || String(q.year) === state.selectedYear;
    const subjectPass = !state.selectedSubject || q.subject === state.selectedSubject;
    const topicPass = !state.selectedTopic || q.topic === state.selectedTopic;
    return yearPass && subjectPass && topicPass;
  });

  const subjects = uniqueSorted(
    state.questions
      .filter((q) => !state.selectedYear || String(q.year) === state.selectedYear)
      .map((q) => q.subject)
      .filter(Boolean)
  );
  fillSelect(subjectSelect, subjects, "All subjects");

  const topics = uniqueSorted(
    state.questions
      .filter(
        (q) =>
          (!state.selectedYear || String(q.year) === state.selectedYear) &&
          (!state.selectedSubject || q.subject === state.selectedSubject)
      )
      .map((q) => q.topic)
      .filter(Boolean)
  );
  fillSelect(topicSelect, topics, "All topics");

  renderQuestions();
  updateYearControls();
}

function renderQuestions() {
  questionList.innerHTML = "";
  countEl.textContent = state.filtered.length;

  const fragment = document.createDocumentFragment();
  state.filtered.forEach((q, idx) => {
    const card = document.createElement("article");
    card.className = "card";

    const yearTag = document.createElement("span");
    yearTag.className = "tag";
    yearTag.textContent = `Asked in NORCET ${q.year}`;

    const title = document.createElement("h3");
    title.textContent = `${idx + 1}. ${q.question_text}`;

    const opts = document.createElement("ol");
    opts.className = "options";

    if (Array.isArray(q.options)) {
      q.options.forEach((opt) => {
        const li = document.createElement("li");
        li.textContent = opt;
        opts.appendChild(li);
      });
    } else {
      ["A", "B", "C", "D"].forEach((key) => {
        if (q.options?.[key]) {
          const li = document.createElement("li");
          li.textContent = `${key}. ${q.options[key]}`;
          opts.appendChild(li);
        }
      });
    }

    card.append(yearTag, title, opts);
    fragment.appendChild(card);
  });

  questionList.appendChild(fragment);
}

yearSelect.addEventListener("change", () => {
  state.selectedYear = yearSelect.value;
  state.selectedSubject = "";
  state.selectedTopic = "";
  applyFilters();
});

subjectSelect.addEventListener("change", () => {
  state.selectedSubject = subjectSelect.value;
  state.selectedTopic = "";
  applyFilters();
});

topicSelect.addEventListener("change", () => {
  state.selectedTopic = topicSelect.value;
  applyFilters();
});

viewPdfBtn.addEventListener("click", () => {
  pdfPanel.classList.remove("hidden");
});

startTestBtn.addEventListener("click", () => {
  alert(`Starting test for ${state.filtered.length} filtered question(s).`);
});

(async function init() {
  state.questions = await loadData();
  const years = uniqueSorted(state.questions.map((q) => q.year).filter(Boolean));
  fillSelect(yearSelect, years, "All years");
  applyFilters();
})();
