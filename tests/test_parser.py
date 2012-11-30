import operator

import py

from rply import ParserGenerator, Token, ParsingError
from rply.token import SourcePosition
from rply.errors import ParserGeneratorWarning

from .base import BaseTests
from .utils import FakeLexer, BoxInt, ParserState


class TestBasic(BaseTests):
    def test_simple(self):
        pg = ParserGenerator(["VALUE"])

        @pg.production("main : VALUE")
        def main(p):
            return p[0]

        parser = pg.build()

        assert False
        assert parser.parse(FakeLexer([Token("VALUE", "abc")])) == Token("VALUE", "abc")

    def test_arithmetic(self):
        pg = ParserGenerator(["NUMBER", "PLUS"])

        @pg.production("main : expr")
        def main(p):
            return p[0]

        @pg.production("expr : expr PLUS expr")
        def expr_op(p):
            return BoxInt(p[0].getint() + p[2].getint())

        @pg.production("expr : NUMBER")
        def expr_num(p):
            return BoxInt(int(p[0].getstr()))

        with self.assert_warns(ParserGeneratorWarning, "1 shift/reduce conflict"):
            parser = pg.build()
        assert parser.parse(FakeLexer([
            Token("NUMBER", "1"),
            Token("PLUS", "+"),
            Token("NUMBER", "4")
        ])) == BoxInt(5)

    def test_null_production(self):
        pg = ParserGenerator(["VALUE", "SPACE"])

        @pg.production("main : values")
        def main(p):
            return p[0]

        @pg.production("values : none")
        def values_empty(p):
            return []

        @pg.production("values : VALUE")
        def values_value(p):
            return [p[0].getstr()]

        @pg.production("values : values SPACE VALUE")
        def values_values(p):
            return p[0] + [p[2].getstr()]

        @pg.production("none :")
        def none(p):
            return None

        parser = pg.build()
        assert parser.parse(FakeLexer([
            Token("VALUE", "abc"),
            Token("SPACE", " "),
            Token("VALUE", "def"),
            Token("SPACE", " "),
            Token("VALUE", "ghi"),
        ])) == ["abc", "def", "ghi"]

        assert parser.parse(FakeLexer([])) == []

    def test_precedence(self):
        pg = ParserGenerator(["NUMBER", "PLUS", "TIMES"], precedence=[
            ("left", ["PLUS"]),
            ("left", ["TIMES"]),
        ])

        @pg.production("main : expr")
        def main(p):
            return p[0]

        @pg.production("expr : expr PLUS expr")
        @pg.production("expr : expr TIMES expr")
        def expr_binop(p):
            return BoxInt({
                "+": operator.add,
                "*": operator.mul
            }[p[1].getstr()](p[0].getint(), p[2].getint()))

        @pg.production("expr : NUMBER")
        def expr_num(p):
            return BoxInt(int(p[0].getstr()))

        parser = pg.build()

        assert parser.parse(FakeLexer([
            Token("NUMBER", "3"),
            Token("TIMES", "*"),
            Token("NUMBER", "4"),
            Token("PLUS",  "+"),
            Token("NUMBER", "5")
        ])) == BoxInt(17)

    def test_per_rule_precedence(self):
        pg = ParserGenerator(["NUMBER", "MINUS"], precedence=[
            ("right", ["UMINUS"]),
        ])

        @pg.production("main : expr")
        def main_expr(p):
            return p[0]

        @pg.production("expr : expr MINUS expr")
        def expr_minus(p):
            return BoxInt(p[0].getint() - p[2].getint())

        @pg.production("expr : MINUS expr", precedence="UMINUS")
        def expr_uminus(p):
            return BoxInt(-p[1].getint())

        @pg.production("expr : NUMBER")
        def expr_number(p):
            return BoxInt(int(p[0].getstr()))

        with self.assert_warns(ParserGeneratorWarning, "1 shift/reduce conflict"):
            parser = pg.build()

        assert parser.parse(FakeLexer([
            Token("MINUS", "-"),
            Token("NUMBER", "4"),
            Token("MINUS", "-"),
            Token("NUMBER", "5"),
        ])) == BoxInt(-9)

    def test_parse_error(self):
        pg = ParserGenerator(["VALUE"])

        @pg.production("main : VALUE")
        def main(p):
            return p[0]

        parser = pg.build()

        with py.test.raises(ParsingError) as exc_info:
            parser.parse(FakeLexer([
                Token("VALUE", "hello"),
                Token("VALUE", "world", SourcePosition(5, 10, 2)),
            ]))

        assert exc_info.value.getsourcepos().lineno == 10

    def test_parse_error_handler(self):
        pg = ParserGenerator(["VALUE"])

        @pg.production("main : VALUE")
        def main(p):
            return p[0]

        @pg.error
        def error_handler(token):
            raise ValueError(token)

        parser = pg.build()

        token = Token("VALUE", "world")

        with py.test.raises(ValueError) as exc_info:
            parser.parse(FakeLexer([
                Token("VALUE", "hello"),
                token
            ]))

        assert exc_info.value.args[0] is token

    def test_state(self):
        pg = ParserGenerator(["NUMBER", "PLUS"], precedence=[
            ("left", ["PLUS"]),
        ])

        @pg.production("main : expression")
        def main(state, p):
            state.count += 1
            return p[0]

        @pg.production("expression : expression PLUS expression")
        def expression_plus(state, p):
            state.count += 1
            return BoxInt(p[0].getint() + p[2].getint())

        @pg.production("expression : NUMBER")
        def expression_number(state, p):
            state.count += 1
            return BoxInt(int(p[0].getstr()))

        parser = pg.build()

        state = ParserState()
        assert parser.parse(FakeLexer([
            Token("NUMBER", "10"),
            Token("PLUS", "+"),
            Token("NUMBER", "12"),
            Token("PLUS", "+"),
            Token("NUMBER", "-2"),
        ]), state=state) == BoxInt(20)
        assert state.count == 6

    def test_error_handler_state(self):
        pg = ParserGenerator([])

        @pg.production("main :")
        def main(state, p):
            pass

        @pg.error
        def error(state, token):
            raise ValueError(state, token)

        parser = pg.build()

        state = ParserState()
        token = Token("VALUE", "")
        with py.test.raises(ValueError) as exc_info:
            parser.parse(FakeLexer([token]), state=state)

        assert exc_info.value.args[0] is state
        assert exc_info.value.args[1] is token
