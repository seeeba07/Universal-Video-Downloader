class QueueManager:
    def __init__(self):
        self._items = []

    def add(self, url, mode, options=None):
        item = {
            "url": str(url),
            "status": "pending",
            "title": str(url),
            "mode": str(mode),
            "options": dict(options or {}),
            "error_message": "",
            "progress": 0.0,
        }
        self._items.append(item)
        return len(self._items) - 1

    def remove(self, index):
        if index < 0 or index >= len(self._items):
            return False

        status = self._items[index]["status"]
        if status not in {"pending", "finished", "error"}:
            return False

        self._items.pop(index)
        return True

    def clear_finished(self):
        before = len(self._items)
        self._items = [
            item for item in self._items
            if item["status"] not in {"finished", "error", "cancelled"}
        ]
        return len(self._items) != before

    def clear_all(self):
        if not self._items:
            return False
        self._items = []
        return True

    def get_next_pending(self):
        for index, item in enumerate(self._items):
            if item["status"] == "pending":
                return index, item
        return None, None

    def get_all(self):
        return self._items

    def count_pending(self):
        return sum(1 for item in self._items if item["status"] == "pending")

    def is_empty(self):
        return len(self._items) == 0

    def update_status(self, index, status, error_message=""):
        if index < 0 or index >= len(self._items):
            return False
        self._items[index]["status"] = str(status)
        self._items[index]["error_message"] = str(error_message)
        return True

    def update_title(self, index, title):
        if index < 0 or index >= len(self._items):
            return False
        self._items[index]["title"] = str(title)
        return True

    def update_progress(self, index, progress):
        if index < 0 or index >= len(self._items):
            return False
        self._items[index]["progress"] = float(max(0.0, min(100.0, progress)))
        return True
