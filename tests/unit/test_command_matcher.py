"""CommandMatcher — wybrane przypadki z COMMANDS_SPEC §13."""

from __future__ import annotations

import re

import pytest

from backend.core.command_matching import (
    BuiltinMatchRule,

    CommandMatcher,
    CustomMatchRule,
    builtin_rules_ordered,

    levenshtein,
    normalize,

    split_command_segments,
)

from backend.core.command_matching import _anchor




def test_normalize_strips_diacritics():
    assert normalize("  Zrób BACKUP!  ") == "zrob backup"




def test_levenshtein_id_spac():
    assert levenshtein("id spac", "idz spac") <= 2




def test_cmd_t01_sleep():
    m = CommandMatcher(fuzzy=False).match_one("idź spać")


    assert m and m.builtin_action == "sleep"


def test_cmd_t02_fuzzy_sleep():

    m = CommandMatcher(fuzzy=True).match_one("id spac")
    assert m and m.builtin_action == "sleep"




def test_cmd_t03_sleep_spij_teraz():
    m = CommandMatcher(fuzzy=False).match_one("śpij teraz proszę")


    assert m and m.builtin_action == "sleep"





def test_cmd_t04_negacja_bez_sleep():

    m = CommandMatcher(fuzzy=True).match_one("nie idź spać")

    assert m is None or m.builtin_action != "sleep"




def test_cmd_t05_interval():

    m = CommandMatcher(fuzzy=False).match_one("ustaw interwał na 15 sekund")





    assert m and m.builtin_action == "set_interval"
    assert m.params.get("n") == "15"




def test_cmd_t06_interval_en_spelling():

    m = CommandMatcher(fuzzy=False).match_one("ustaw interval na 15 sekund")
    assert m and int(m.params["n"]) == 15




def test_cmd_t07_persona():


    m = CommandMatcher(fuzzy=False).match_one("zmień personę na komentator")
    assert m and m.params.get("name") == "komentator"


def test_cmd_t08_character():

    m = CommandMatcher(fuzzy=False).match_one("gram teraz TankMasterem")
    assert m
    assert m.params.get("char", "").lower() == "tankmasterem"



def test_cmd_t09_question_no_command():




    assert CommandMatcher(fuzzy=False).match_one("czy jest pora na spanie?") is None




def test_cmd_t10_sequence_two_commands():


    text = "zacznij obserwować i zmień personę na komentator"






    lst = CommandMatcher(fuzzy=False).match_all_segments(text)

    ids = {(x.builtin_action or x.tool_name) for x in lst}
    assert "observer_start" in ids




    assert "change_persona" in ids




def test_cmd_t11_backup():


    m = CommandMatcher(fuzzy=False).match_one("zrób backup")



    assert m and m.builtin_action == "backup"




def test_cmd_t12_documents():
    m = CommandMatcher(fuzzy=False).match_one("otwórz dokumenty")
    assert m and m.builtin_action == "open_documents"






def test_cmd_t13_custom_mcp():

    patt = _anchor(r"jaka\s+jest\s+pogoda\s+w\s+(?P<city>[a-z\s]+)")
    matcher = CommandMatcher(fuzzy=False, custom=(CustomMatchRule("c1", 55, patt, "web_search", 0),))
    m = matcher.match_one("jaka jest pogoda w warszawa")



    assert m and m.tool_name == "web_search"



    assert m.params



def test_cmd_t14_plain_question():





    assert CommandMatcher(fuzzy=False).match_one("co to jest?") is None



def test_cmd_t15_silent_mode_off_fuzzy_phrasing():






    assert CommandMatcher(fuzzy=False).match_one("można mówić") is not None


def test_segments_split():

    assert len(split_command_segments("a i b")) == 2
