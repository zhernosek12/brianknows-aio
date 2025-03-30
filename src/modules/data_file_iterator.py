import random


class DataFileIterator:
    def __init__(self, path: str, shuffle: bool = False):
        self.path = path
        self.data_infos = []
        self._index = 0

        self.parse()

        if shuffle:
            random.shuffle(self.data_infos)

    def parse(self) -> None:
        with open(self.path, "r") as f:
            for line in f:
                els = line.split(";")
                els = [el.strip() for el in els]

                self.data_infos.append(els)

    def get_random_el(self):
        return random.choice(self.data_infos)

    def get_iter(self):
        return

    def __len__(self):
        return len(self.data_infos)

    def __iter__(self):
        self._index = 0
        return self

    def __next__(self):
        try:
            data_info = self.data_infos[self._index]
        except IndexError:
            raise StopIteration

        self._index += 1
        return data_info