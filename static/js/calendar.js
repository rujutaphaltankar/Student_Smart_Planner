// ==========================================================
// Student Smart Planner - Calendar Rendering
// Builds a simple month-grid calendar from the `events` array
// injected by calendar.html (each: {title, start: 'YYYY-MM-DD', type}).
// ==========================================================

let currentDate = new Date();
let selectedDate = formatDateKey(currentDate);

function formatDateKey(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function formatReadableDate(dateKey) {
    const [year, month, day] = dateKey.split('-').map(Number);
    return new Date(year, month - 1, day).toLocaleDateString(undefined, {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric'
    });
}

function renderCalendar(animate) {
    const grid = document.getElementById('calendarGrid');
    const label = document.getElementById('calendarMonthLabel');
    if (!grid || !label) return;

    grid.classList.remove('calendar-refresh');
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
        const cell = document.createElement('button');
        cell.type = 'button';
        cell.className = 'calendar-cell';

        const cellDate = new Date(year, month, day);
        const isToday = cellDate.toDateString() === today.toDateString();
        if (isToday) cell.classList.add('today');
        const dateKey = formatDateKey(cellDate);
        if (dateKey === selectedDate) cell.classList.add('selected');
        cell.setAttribute('aria-pressed', String(dateKey === selectedDate));
        cell.setAttribute('aria-label', `${formatReadableDate(dateKey)}${(eventsByDate[dateKey] || []).length ? `, ${(eventsByDate[dateKey] || []).length} events` : ''}`);
        cell.addEventListener('click', function () {
            selectedDate = dateKey;
            renderCalendar();
            renderSelectedDate();
        });

        const dateLabel = document.createElement('div');
        dateLabel.className = 'date-num';
        dateLabel.textContent = day;
        cell.appendChild(dateLabel);

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

    if (animate) {
        void grid.offsetWidth;
        grid.classList.add('calendar-refresh');
    }
}

function renderSelectedDate() {
    const dateLabel = document.getElementById('selectedDateLabel');
    const eventList = document.getElementById('selectedDateEvents');
    const eventDateInput = document.getElementById('calendarEventDate');
    if (!dateLabel || !eventList || !eventDateInput) return;

    dateLabel.textContent = formatReadableDate(selectedDate);
    eventDateInput.value = selectedDate;
    eventList.replaceChildren();

    const selectedEvents = (events || []).filter(function (event) {
        return event.start === selectedDate;
    });

    if (!selectedEvents.length) {
        const emptyMessage = document.createElement('p');
        emptyMessage.className = 'text-muted mb-0';
        emptyMessage.textContent = 'Nothing planned for this date yet.';
        eventList.appendChild(emptyMessage);
        return;
    }

    selectedEvents.forEach(function (event) {
        const item = document.createElement('div');
        item.className = 'selected-event-item';

        const content = document.createElement('div');
        content.className = 'selected-event-content';

        const title = document.createElement('strong');
        title.textContent = event.title;
        content.appendChild(title);

        const type = document.createElement('span');
        type.className = `badge calendar-type-${event.type}`;
        type.textContent = {
            task: 'Task',
            exam: 'Exam',
            study: 'Study session',
            event: 'Personal event'
        }[event.type] || 'Event';
        content.appendChild(type);

        if (event.description) {
            const description = document.createElement('p');
            description.className = 'text-muted mb-0';
            description.textContent = event.description;
            content.appendChild(description);
        }

        item.appendChild(content);

        if (event.type === 'event' && event.delete_url) {
            const deleteForm = document.createElement('form');
            deleteForm.method = 'POST';
            deleteForm.action = event.delete_url;
            deleteForm.addEventListener('submit', function (submitEvent) {
                if (!window.confirm('Delete this calendar event?')) {
                    submitEvent.preventDefault();
                }
            });

            const deleteButton = document.createElement('button');
            deleteButton.type = 'submit';
            deleteButton.className = 'btn btn-sm btn-outline-danger';
            deleteButton.setAttribute('aria-label', `Delete ${event.title}`);
            deleteButton.title = 'Delete event';
            deleteButton.innerHTML = '<i class="bi bi-trash"></i>';
            deleteForm.appendChild(deleteButton);
            item.appendChild(deleteForm);
        }

        eventList.appendChild(item);
    });
}

document.addEventListener('DOMContentLoaded', function () {
    renderCalendar();
    renderSelectedDate();

    const prevBtn = document.getElementById('prevMonth');
    const nextBtn = document.getElementById('nextMonth');

    if (prevBtn) {
        prevBtn.addEventListener('click', function () {
            currentDate.setMonth(currentDate.getMonth() - 1);
            renderCalendar(true);
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', function () {
            currentDate.setMonth(currentDate.getMonth() + 1);
            renderCalendar(true);
        });
    }
});
