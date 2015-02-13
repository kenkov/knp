#! /usr/bin/env python
# coding:utf-8

# from collections import defaultdict
import subprocess
import re


class KNP:
    def __init__(
        self,
        juman_command="juman",
        knp_command="knp",
        option: list=[],
    ):
        self.juman = subprocess.Popen(
            [juman_command] + option,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        self.knp = subprocess.Popen(
            [knp_command, "-tab", "-anaphora"] + option,
            stdin=self.juman.stdout,
            stdout=subprocess.PIPE
        )

    def parse(self, ipt: str) -> [(str, str)]:
        _ipt = ipt + "\n"
        self.juman.stdin.write(_ipt.encode('utf-8'))
        self.juman.stdin.flush()
        ans = []
        for _line in self.knp.stdout:
            line = _line.decode('utf-8').rstrip()
            self.knp.stdout.flush()
            if line == "EOS":
                break
            else:
                ans.append(line)
        # morph = self.knp.stdout.readline().decode('utf-8').rstrip()
        return ans


class KNPAnalyzer:
    def __init__(
        self,
        juman_command="juman",
        knp_command="knp",
        option: list=[]
    ):
        self.knp = KNP(juman_command, knp_command)

        # 新しい文の始まり
        self.sent_regex = re.compile(r"^#")
        # 文節
        self.clause_regex = re.compile(r"^\*")
        # 基本句
        #   KNP が格解析などの処理を行う基本単位
        self.phrase_regex = re.compile(r"^\+")

        # feature
        self.feature_regex = re.compile(r"<([^<>]+)>")

    def _analyze(
        self,
        lst: [str],
    ):
        tree = Tree()
        clause_id, phrase_id = 0, 0
        clauses, phrases = [], []

        for text in lst:
            clause_flag = True if self.clause_regex.search(text) else False
            phrase_flag = True if self.phrase_regex.search(text) else False
            sent_flag = True if self.sent_regex.search(text) else False
            morph_flag = not (clause_flag or phrase_flag or sent_flag)

            if clause_flag:
                clause = Clause(clause_id, text)
                tree.add(clause)
                clauses.append(clause)
                clause_id += 1
            elif phrase_flag:
                phrase = Phrase(phrase_id, text)
                clause.add(phrase)
                phrases.append(phrase)
                phrase_id += 1
            elif morph_flag:
                morph = Morph(text, [], [])
                phrase.add(morph)

        # set links
        for clause in tree:
            if clause.next_link_id != -1:
                clauses[clause.next_link_id].add_prev_link(
                    clause.id,
                    clause
                )
            for phrase in clause:
                if phrase.next_link_id != -1:
                    phrases[phrase.next_link_id].add_prev_link(
                        phrase.id,
                        phrase
                    )

        return tree

    def analyze(
        self,
        lst: list
    ):
        return self._analyze(self.knp.parse(lst))


class Tree:
    def __init__(
        self,
    ):
        self.clauses = []
        self.clause_size = 0

    def __iter__(self):
        return iter(self.clauses)

    def add(self, clause):
        self.clauses.append(clause)
        self.clause_size += 1


class Clause:
    def __init__(
        self,
        _id,
        clause_info: str,
    ):
        self.id = _id
        self.clause_info = clause_info
        self.phrases = []
        self.phrase_size = 0

        self.prev_link_ids = []
        self.prev_links = []

        self.next_link_id = int(clause_info.split()[1][:-1])
        # set features
        _features = re.findall(r"<([^<>]+)>", clause_info)
        self.features = self.feat2dic(_features)

    def __iter__(self):
        return iter(self.phrases)

    def __str__(self):
        return "{}: link to {} from {} {}".format(
            self.id, self.next_link_id, self.prev_link_ids,
            self.features
        )

    def add(self, phrase):
        self.phrases.append(phrase)
        self.phrase_size += 1

    def add_prev_link(self, _id, item):
        self.prev_link_ids.append(_id)
        self.prev_links.append(item)

    def feat2dic(self, features):
        flt = {
            re.compile(r"(モダリティ)-(.+)"),
            re.compile(r"(用言):(.+)"),
            re.compile(r"(体言)()"),
            re.compile(r"(係):(.+)"),
        }

        dic = dict()
        for feature in features:
            for regex in flt:
                dic.update(regex.findall(feature))
        return dic


class Phrase:
    def __init__(
        self,
        _id,
        phrase_info: str,
    ):
        self.id = _id
        self.phrase_info = phrase_info
        self.morphs = []
        self.morph_size = 0

        self.prev_link_ids = []
        self.prev_links = []

        self.next_link_id = int(phrase_info.split()[1][:-1])
        # set features
        _features = re.findall(r"<([^<>]+)>", phrase_info)
        self.features = self.feat2dic(_features)

    def __iter__(self):
        return iter(self.morphs)

    def add(self, morph):
        self.morphs.append(morph)
        self.morph_size += 1

    def add_prev_link(self, _id, item):
        self.prev_link_ids.append(_id)
        self.prev_links.append(item)

    def __str__(self):
        return "{}: link to {} from {} {}".format(
            self.id, self.next_link_id, self.prev_link_ids,
            self.features
        )

    def feat2dic(self, features):
        flt = {
            re.compile(r"(モダリティ)-(.+)"),
            re.compile(r"(用言):(.+)"),
            re.compile(r"(体言)()"),
            re.compile(r"(係):(.+)"),
            re.compile(r"(述語項構造):(.+)"),
            re.compile(r"(EID):(.+)"),
        }

        dic = dict()
        for feature in features:
            for regex in flt:
                dic.update(regex.findall(feature))
        return dic


class Morph:
    def __init__(
        self,
        # "動か うごか 動く 動詞 2 * 0 子音動詞カ行 2 未然形".split()
        morph_info: str,
        # "代表表記:動く/うごく 自他動詞:他:動かす/うごかす 反義:動詞:止まる/とまる".split()
        additional_info: list,
        feature_info: list,  # <...><...><...>
    ):

        self.morph_info = morph_info
        self.additional_info = additional_info
        self.feature_info = feature_info

        morph_lst = morph_info.split()[:10]

        self.surface = morph_lst[0]
        self.yomi = morph_lst[1]
        self.genkei = morph_lst[2]
        self.pos = morph_lst[3]
        # type of verb conjugation
        self.con_type = morph_lst[7]
        # form of verb conjugation
        self.con_form = morph_lst[9]
        # normalized_surface
        # self.normalized_surface = normalized_surface

        # additional info
        add_info = re.findall(r'"([^"]+)"', morph_info)
        self.additional_info = add_info[0].split() if add_info else []
        # feature
        _features = re.findall(r"<([^<>]+)>", morph_info)
        self.features = self.feat2dic(_features)

    def __str__(self):
        return "{}/{} {}".format(
            self.surface, self.pos,  # self.additional_info,
            self.features
        )

    def feat2dic(self, features):
        flt = {
            re.compile(r"^(Wikipedia\w+):(.+)"),
            re.compile(r"^(ドメイン):(.+)"),
            re.compile(r"^(カテゴリ):(.+)"),
            re.compile(r"^(代表表記):(.+)"),
            re.compile(r"^(係):(.+)"),
        }
        dic = dict()
        for feature in features:
            for regex in flt:
                dic.update(regex.findall(feature))

        # 代表表記がないものは surface/surface をかわりに使う
        if "代表表記" not in dic:
            dic.update({"代表表記": "{}/{}".format(self.surface, self.surface)})
        return dic


if __name__ == '__main__':
    import sys

    fd = open(sys.argv[1]) if len(sys.argv) >= 2 else sys.stdin

    knp = KNPAnalyzer(knp_command="/home/kenkov/knp/bin/knp")
    for text in (_.strip() for _ in fd):
        print(text)
        tree = knp.analyze(text)
        for clause in tree:
            print("  {}".format(clause))
            for phrase in clause:
                print("    {}".format(phrase))
                for morph in phrase:
                    print("      {}".format(morph))
