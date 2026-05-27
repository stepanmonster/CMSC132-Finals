"""
Instruction encoder for the CMSC132 ISA simulator.

Provides:
- Global operation tables (operations, operationCodes)
- Instruction.decodeMSG: decode encoded message text tokens
- Instruction.encodeOp: encode one operand into 10-bit mode+address form
- Instruction.encode: encode one assembly line into a 32-bit instruction word
- Instruction.encodeProgram: parse program lines and place encoded words in memory
"""

from bin_convert import HalfPrecision, Length
from storage import memory, register, variable


# Operations grouped by Execute/Write bit groups.
# Group index maps to operationCodes[0].
operations = [
    ["PRNT", "EOP", "FUNC"],
    ["MOV", "CALL", "RET", "SCAN", "ADDPC"],
    ["JZ", "JNZ", "JL", "JLE", "JG", "JGE", "J", "JMP"],
    ["MOD", "ADD", "SUB", "MUL", "DIV", "CB", "CF", "CMP"],
]

# operationCodes[0] = Execute+Write bits by operation group
# operationCodes[1] = Category codes used inside each group
operationCodes = [
    ["00", "01", "10", "11"],
    ["000", "001", "010", "011", "100", "101", "110", "111"],
]


class Instruction:
    """Assembler-style instruction encoder."""

    _OPCODE_MAP = {
        "PRNT": "00000",
        "EOP": "00001",
        "FUNC": "00001",
        "MOV": "01000",
        "CALL": "01001",
        "RET": "01010",
        "SCAN": "01011",
        "JZ": "10000",
        "JEQ": "10000",
        "JNZ": "10001",
        "JNE": "10001",
        "JL": "10010",
        "JLT": "10010",
        "JLE": "10011",
        "JG": "10100",
        "JGT": "10100",
        "JGE": "10101",
        "J": "10110",
        "JMP": "10110",
        "MOD": "11000",
        "ADD": "11001",
        "SUB": "11010",
        "MUL": "11011",
        "DIV": "11100",
        "CB": "11001",
        "CF": "11001",
        "CMP": "11010",
        "ADDPC": "01000",
    }

    _REGISTER_NAMES = {"BR", "XR", "ACC", "IR", "PC", "JR", "CR"}

    @staticmethod
    def _is_number(text):
        try:
            float(text)
            return True
        except Exception:
            return False

    @staticmethod
    def _is_register_symbol(sym):
        usym = sym.upper()
        if usym in Instruction._REGISTER_NAMES:
            return True
        if usym.startswith("R") and usym[1:].isdigit():
            return True
        return False

    @staticmethod
    def _resolve_symbol_or_int(token):
        t = token.strip()
        ut = t.upper()
        if ut in variable.data:
            return int(variable.data[ut])
        if Instruction._is_number(t):
            return int(float(t))
        raise ValueError(f"Unknown operand/address token: {token}")

    @staticmethod
    def _to_addr7(value):
        iv = int(value)
        return bin(iv & 0x7F).replace("0b", "").zfill(Length.opAddr)

    @staticmethod
    def _to_disp7(value):
        iv = int(value)
        sign = "1" if iv < 0 else "0"
        mag = abs(iv) & 0x3F
        return sign + bin(mag).replace("0b", "").zfill(Length.opAddr - 1)

    @staticmethod
    def _split_inst(inst):
        text = inst.strip()
        if not text:
            return "", []

        parts = text.split(None, 1)
        op = parts[0].upper()
        if len(parts) == 1:
            return op, []

        tail = parts[1].strip()

        # Prefer comma-separated operands; otherwise use whitespace split.
        if "," in tail:
            operands = [p.strip() for p in tail.split(",") if p.strip()]
        else:
            operands = [p.strip() for p in tail.split() if p.strip()]

        return op, operands

    @staticmethod
    def _extract_msg(line):
        idx = line.find("M:")
        if idx == -1:
            return line, None
        code = line[:idx].rstrip()
        msg = line[idx + 2 :].strip()
        return code, msg

    @staticmethod
    def _queue_message(msg):
        decoded = Instruction.decodeMSG(msg)
        q = variable.data.get("MSG", {})
        next_index = len(q)
        q[next_index] = decoded
        variable.data["MSG"] = q

    @staticmethod
    def decodeMSG(msg):
        """Decode message placeholders into printable control characters.

        Replacements:
        - 'minus' -> '-'
        - 'under' -> '_'
        - '-_' -> newline
        - '-' -> space
        - '_' -> tab
        """
        out = str(msg)
        out = out.replace("minus", "-")
        out = out.replace("under", "_")
        out = out.replace("-_", "\n")
        out = out.replace("-", " ")
        out = out.replace("_", "\t")
        return out

    @staticmethod
    def encodeOp(operand):
        """Encode one operand.

        Immediate (numeric) operands return 16-bit Half Precision binary.
        Non-immediate operands return 10-bit mode+address encoding.
        """
        token = operand.strip()

        # Immediate value
        if Instruction._is_number(token):
            return HalfPrecision.hpdec2bin(float(token))

        # Message token (optional feature)
        if "M:" in token:
            raw = token.split("M:", 1)[1]
            Instruction._queue_message(raw)
            return "0" * Length.operand

        # Parenthesized forms
        if token.startswith("(") and token.endswith(")"):
            inner = token[1:-1].strip()
            uinner = inner.upper()

            # Relative / Based / Indexed group
            if "X" in uinner or "Y" in uinner or "Z" in uinner:
                if "X" in uinner:
                    marker = "X"
                    mode = "100"
                elif "Y" in uinner:
                    marker = "Y"
                    mode = "000"  # used with rb=1 to mean based
                else:
                    marker = "Z"
                    mode = "100"  # used with rb=1 to mean relative

                rem = uinner.replace(marker, "", 1).strip()
                if not rem:
                    rem = "0"

                if rem in variable.data:
                    addr = Instruction._to_addr7(variable.data[rem])
                elif Instruction._is_number(rem):
                    addr = Instruction._to_disp7(int(float(rem)))
                else:
                    addr = Instruction._to_addr7(Instruction._resolve_symbol_or_int(rem))

                return (mode + addr).zfill(Length.operand)

            # Auto inc / dec, register-indirect, indirect
            if "+" in inner:
                rem = inner.replace("+", "").strip()
                addr = Instruction._to_addr7(Instruction._resolve_symbol_or_int(rem))
                return ("110" + addr).zfill(Length.operand)

            if "-" in inner:
                rem = inner.replace("-", "").strip()
                addr = Instruction._to_addr7(Instruction._resolve_symbol_or_int(rem))
                return ("111" + addr).zfill(Length.operand)

            if Instruction._is_register_symbol(inner):
                addr = Instruction._to_addr7(Instruction._resolve_symbol_or_int(inner))
                return ("001" + addr).zfill(Length.operand)

            addr = Instruction._to_addr7(Instruction._resolve_symbol_or_int(inner))
            return ("011" + addr).zfill(Length.operand)

        # Non-parenthesized: register or direct memory
        if Instruction._is_register_symbol(token):
            addr = Instruction._to_addr7(Instruction._resolve_symbol_or_int(token))
            return ("000" + addr).zfill(Length.operand)

        addr = Instruction._to_addr7(Instruction._resolve_symbol_or_int(token))
        return ("010" + addr).zfill(Length.operand)

    @staticmethod
    def _normalize_operation(op, operands):
        """Apply operation simplifications and implicit operands."""
        out_op = op.upper()
        out_operands = list(operands)

        if out_op in ("CB", "CF"):
            if len(out_operands) == 1:
                out_operands.append("BR")
            out_op = "ADD"

        elif out_op == "CMP":
            src = out_operands[0] if out_operands else "0"
            out_operands = ["JR", src]
            out_op = "SUB"

        elif out_op == "ADDPC":
            # Move relative(0) value into destination.
            dst = out_operands[0] if out_operands else "ACC"
            out_operands = [dst, "(Z0)"]
            out_op = "MOV"

        elif out_op == "CALL":
            fn = out_operands[0] if out_operands else "0"
            out_operands = ["PC", fn]

        elif out_op == "RET":
            retv = out_operands[0] if out_operands else "ACC"
            out_operands = ["ACC", retv]

        elif out_op == "PRNT":
            # Runtime prints operand 2 when execute=0 and write=0.
            if len(out_operands) == 1:
                out_operands = ["ACC", out_operands[0]]

        return out_op, out_operands

    @staticmethod
    def encode(inst):
        """Encode one instruction string to a 32-bit instruction code."""
        text = inst.strip()
        if not text:
            return "0" * Length.instrxn

        op, operands = Instruction._split_inst(text)
        if not op:
            return "0" * Length.instrxn

        # FUNC uses the sentinel all-zeros instruction.
        if op.upper() == "FUNC":
            return "0".zfill(Length.instrxn)

        op, operands = Instruction._normalize_operation(op, operands)

        opcode = Instruction._OPCODE_MAP.get(op.upper())
        if opcode is None:
            raise ValueError(f"Unknown operation: {op}")

        ib = "0"
        rb = "0"
        extra = "0" * 5

        # Operand 1
        if len(operands) >= 1:
            op1_code = Instruction.encodeOp(operands[0])
            if len(op1_code) == Length.precision:
                # Fallback: immediate in op1 is not ISA-standard, force direct zero.
                op1_code = "010" + "0" * Length.opAddr
        else:
            op1_code = "0" * Length.operand

        # Operand 2
        if len(operands) >= 2:
            op2_raw = operands[1].strip()
            op2_encoded = Instruction.encodeOp(op2_raw)

            if len(op2_encoded) == Length.precision:
                ib = "1"
                op2_code = "0" * Length.operand
                extra = op2_encoded[-5:]
            else:
                op2_code = op2_encoded

                # rb is used for relative/based forms in operand 2.
                p = op2_raw.strip().upper()
                if p.startswith("(") and p.endswith(")"):
                    pin = p[1:-1]
                    if "Y" in pin or "Z" in pin:
                        rb = "1"
                        if "Y" in pin:
                            # Based is decoded when op2 mode is 000..011.
                            op2_code = "000" + op2_code[3:]
                        elif "Z" in pin:
                            # Relative is decoded when op2 mode is 100..111.
                            op2_code = "100" + op2_code[3:]
        else:
            op2_code = "0" * Length.operand

        full = opcode + ib + op1_code + rb + op2_code + extra
        return full.zfill(Length.instrxn)

    @staticmethod
    def encodeProgram(program):
        """Encode all instructions and store them to memory.

        CB/CF instructions are encoded and inserted at the start of the output
        sequence to simplify block jumps, while preserving the rest in order.
        """
        start_addr = register.load(variable.data["BR"])
        current_addr = start_addr

        encoded = []
        block_count = 0
        in_multiline_comment = False

        for raw in program:
            line = raw.rstrip("\n")
            stripped = line.strip()

            if not stripped:
                continue

            first = stripped[0].lower()
            if first == "z":
                in_multiline_comment = not in_multiline_comment
                continue
            if in_multiline_comment:
                continue
            if first == "x":
                continue

            code_part, maybe_msg = Instruction._extract_msg(stripped)
            if maybe_msg:
                Instruction._queue_message(maybe_msg)

            op, operands = Instruction._split_inst(code_part)
            if not op:
                continue

            uop = op.upper()

            if uop in ("CB", "CF") and operands:
                # Store current instruction address to the block slot.
                block_sym = operands[0].upper()
                if block_sym in variable.data:
                    memory.store(variable.data[block_sym], current_addr)

                inst_code = Instruction.encode(code_part)
                encoded.insert(block_count, inst_code)
                block_count += 1
            else:
                inst_code = Instruction.encode(code_part)
                encoded.append(inst_code)

            current_addr += 1

        # Store number of blocks in BR as required by the ISA design.
        register.store(variable.data["BR"], block_count)

        # Write encoded program words to memory starting at the original BR address.
        for i, code in enumerate(encoded):
            memory.store(start_addr + i, code)
