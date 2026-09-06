// ==========================================================
// Student Smart Planner - Calendar Rendering
// Builds a simple month-grid calendar from the `events` array
// injected by calendar.html (each: {title, start: 'YYYY-MM-DD', type}).
// ==========================================================

let currentDate = new Date();

function renderCalendar() {
    const grid = document.getElementById('calendarGrid');
    const label = document.getElementById('calendarMonthLabel');
    if (!grid || !label) return;

    grid.innerHTML = '';

    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();

    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'];
    label.textContent = `${monthNames[month]} ${year}`;

    // Day-of-week headers
    ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].forEach(function (day) {
        const dayNameEl = document.createElement('div');
        dayNameEl.className = 'calendar-day-name';
        dayNameEl.textContent = day;
        grid.appendChild(dayNameEl);
    });

    const firstDayOfMonth = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const today = new Date();

    // Empty cells before the 1st
    for (let i = 0; i < firstDayOfMonth; i++) {
        const emptyCell = document.createElement('div');
        emptyCell.className = 'calendar-cell empty';
        grid.appendChild(emptyCell);
    }

    // Group events by date string for quick lookup
    const eventsByDate = {};
    (events || []).forEach(function (ev) {
        if (!eventsByDate[ev.start]) eventsByDate[ev.start] = [];
        eventsByDate[ev.start].push(ev);
    });

    for (let day = 1; day <= daysInMonth; day++) {
        const cell = document.createElement('div');
        cell.className = 'calendar-cell';

        const cellDate = new Date(year, month, day);
        const isToday = cellDate.toDateString() === today.toDateString();
        if (isToday) cell.classList.add('today');

        const dateLabel = document.createElement('div');
        dateLabel.className = 'date-num';
        dateLabel.textContent = day;
        cell.appendChild(dateLabel);

        const dateKey = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const dayEvents = eventsByDate[dateKey] || [];

        dayEvents.slice(0, 3).forEach(function (ev) {
            const dot = document.createElement('span');
            dot.className = 'calendar-event-dot event-' + ev.type;
            dot.textContent = ev.title;
            dot.title = ev.title;
            cell.appendChild(dot);
        });

        if (dayEvents.length > 3) {
            const more = document.createElement('span');
            more.className = 'text-muted';
            more.style.fontSize = '0.68rem';
            more.textContent = `+${dayEvents.length - 3} more`;
            cell.appendChild(more);
        }

        grid.appendChild(cell);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    renderCalendar();

    const prevBtn = document.getElementById('prevMonth');
    const nextBtn = document.getElementById('nextMonth');

    if (prevBtn) {
        prevBtn.addEventListener('click', function () {
            currentDate.setMonth(currentDate.getMonth() - 1);
            renderCalendar();
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', function () {
            currentDate.setMonth(currentDate.getMonth() + 1);
            renderCalendar();
        });
    }
});
