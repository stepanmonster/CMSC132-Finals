"""
Program runner for the CMSC132 ISA simulator.

Contains the fetch-decode-execute loop that reads encoded 32-bit instructions
from memory, resolves operands via addressing modes, performs arithmetic/logic
operations, and writes results back. Also defines a lightweight exception class
for runtime error handling (e.g., division by zero).

Instruction format (32 bits):
  Bit:   0    1    2-4    5     6-8      9-15      16    17-19     20-26     27-31
        [Exe] [Wr]  [Cat]  [ib]  [Op1Mode] [Op1Addr] [rb]  [Op2Mode] [Op2Addr] [Extra]
  Exe = Execute bit, Wr = Write bit, Cat = Category, ib = Immediate bit
  rb = Relative/Based bit for Op2

Dependencies: storage, bin_convert, compiler, addressing
"""
from storage import memory, register, variable
from bin_convert import HalfPrecision, Length
from compiler import Instruction
from addressing import AddressingMode, Access


class Except:
    """Lightweight exception wrapper with occurrence tracking and return values."""

    def __init__(self, msg, occur=True):
        self.message = msg
        self.occur = occur
        self.ret = None

    def dispMSG(self):
        """Print the exception message."""
        print(self.message)

    def isOccur(self):
        """Return True if this exception has occurred."""
        return self.occur

    def setReturn(self, value):
        """Store a return value associated with the exception."""
        self.ret = value

    def getReturn(self):
        """Retrieve the stored return value."""
        return self.ret


class Program:
    """Main ISA simulator engine — encodes, fetches, decodes, and executes instructions."""

    def __init__(self, program):
        """Encode a list of assembly instruction strings into memory.

        Delegates to Instruction.encodeProgram(), which parses each line,
        converts to 32-bit binary, and stores sequentially in memory starting
        at the Base Register address.
        """
        Instruction.encodeProgram(program)

    @staticmethod
    def exception(name, value):
        """Handle runtime exceptions during execution.

        Currently supports 'DivByZero':
        - Both operands zero       -> 'Infinity'
        - Only operand two is zero -> 'undefined'
        """
        if name == 'DivByZero':
            op1, op2 = value
            if op1 == 0 and op2 == 0:
                return 'Infinity'
            if op2 == 0:
                return 'undefined'
        return None

    def _get_movecode(self, opcode):
        """Determine the write-mode code from the 5-bit opcode.

        movecode 1 = CALL (PC -> CR, then source -> destination)
        movecode 2 = RET  (CR -> PC, then source -> destination)
        movecode 3 = SCAN (input message -> destination)
        movecode 0 = default (direct source -> destination)
        """
        if opcode[0] == '0' and opcode[1] == '1':
            if opcode[2:5] == '001':
                return 1
            if opcode[2:5] == '010':
                return 2
            if opcode[2:5] == '011':
                return 3
        return 0

    def getOp(self, mode_bits, addr_bits, op_num=1):
        """Resolve an operand's effective address and value using its 3-bit mode code.

        Dispatches to the appropriate AddressingMode method based on the mode:
        000 = Register      001 = Register Indirect      010 = Direct
        011 = Indirect      100/101 = Indexed            110 = Auto-Increment
        111 = Auto-Decrement

        Returns a tuple (effective_address, value, storage_type) where
        storage_type is 'register' or 'memory' (used by write()).
        """
        addr_int = int(addr_bits, 2)

        if mode_bits == '000':
            eff, val, _ = AddressingMode.register(addr_int)
            return (eff, val, 'register')
        if mode_bits == '001':
            eff, val = AddressingMode.register_indirect(addr_int)
            return (eff, val, 'memory')
        if mode_bits == '010':
            eff, val = AddressingMode.direct(addr_int)
            return (eff, val, 'memory')
        if mode_bits == '011':
            eff, val = AddressingMode.indirect(addr_int)
            return (eff, val, 'memory')
        if mode_bits in ('100', '101'):
            eff, val = AddressingMode.indexed(addr_bits)
            return (eff, val, 'memory')
        if mode_bits == '110':
            eff, val = AddressingMode.autoinc(addr_int)
            return (eff, val, 'memory')
        if mode_bits == '111':
            eff, val = AddressingMode.autodec(addr_int)
            return (eff, val, 'memory')

        return (None, None, None)

    def execute(self, result, opcode):
        """Perform the operation dictated by the opcode on the resolved operand values.

        Write-bit = 1: Arithmetic (MOD/ADD/SUB/MUL/DIV) based on category code.
                       Division/mod by zero triggers the DivByZero exception handler.
        Execute-bit = 1, Write-bit = 0: Jump comparison against JR.
                       Category determines which comparison (EQ/NE/LT/LE/GT/GE/JMP).
        """
        exec_bit = opcode[0]
        write_bit = opcode[1]
        category = opcode[2:5]

        if write_bit == '1':
            op1, op2 = result
            if category == '000':
                return self.__class__.exception('DivByZero', (op1, op2)) if op2 == 0 else op1 % op2
            if category == '001':
                return op1 + op2
            if category == '010':
                return op1 - op2
            if category == '011':
                return op1 * op2
            if category == '100':
                return self.__class__.exception('DivByZero', (op1, op2)) if op2 == 0 else op1 / op2

        if exec_bit == '1' and write_bit == '0':
            jr = register.load(variable.data["JR"])
            if category == '000':
                return jr == 0
            if category == '001':
                return jr != 0
            if category == '010':
                return jr < 0
            if category == '011':
                return jr <= 0
            if category == '100':
                return jr > 0
            if category == '101':
                return jr >= 0
            if category == '110':
                return True

        return None

    def write(self, dest, src, movecode):
        """Write a value to a destination storage location.

        dest = (storage_type, address) tuple from getOp()
        movecode determines special write behavior:
        1 = CALL: save PC to CR, then store src
        2 = RET:  restore PC from CR, then store src
        3 = SCAN: pull next message from MSG buffer, store that instead of src
        0 = default: direct store
        """
        typ, addr = dest
        if movecode == 1:
            pc_val = register.load(variable.data["PC"])
            register.store(variable.data["CR"], pc_val)
            Access.store(typ, addr, src)
        elif movecode == 2:
            cr_val = register.load(variable.data["CR"])
            register.store(variable.data["PC"], cr_val)
            Access.store(typ, addr, src)
        elif movecode == 3:
            mi = variable.data["MI"]
            msg_dict = variable.data["MSG"]
            msg_val = msg_dict.get(mi, "")
            variable.data["MI"] = mi + 1
            Access.store(typ, addr, msg_val)
        else:
            Access.store(typ, addr, src)

    def run(self):
        """Main fetch-decode-execute loop.

        Each cycle:
        1. FETCH   — Load IR (Instruction Register) to get the current address,
                     then load the 32-bit instruction string from memory.
        2. DECODE  — Split the 32-bit string into opcode, operand modes, addresses,
                     and special flags (ib = immediate bit, rb = relative/based bit).
                     Resolve operand 1 via getOp() and operand 2 via either
                     immediate, relative/based, or standard addressing.
        3. EXECUTE — If Execute bit is set, perform arithmetic (write=1) or
                     jump comparison (write=0). For jumps, update PC to the
                     target address if the condition is met.
        4. WRITE   — If Write bit is set, store the result back to the destination.
        5. PRINT   — If neither bit is set (PRNT/EOP), output the value.
        6. ADVANCE — Increment PC and update IR (unless a jump was taken).

        Terminates when the instruction is not a valid 32-bit string or is all
        zeros (EOP/FUNC sentinel).
        """
        ir_addr = variable.data["IR"]
        pc_addr = variable.data["PC"]

        while True:
            ir = register.load(ir_addr)
            inscode = memory.load(ir)

            if not isinstance(inscode, str) or len(inscode) != Length.instrxn or inscode == "0" * Length.instrxn:
                break

            opcode = inscode[0:5]
            exec_bit = inscode[0]
            write_bit = inscode[1]
            ib = inscode[5]
            rb = inscode[16]

            op1_eff, op1_val, op1_stor = self.getOp(inscode[6:9], inscode[9:16], 1)

            op2_val = None
            if ib == '1':
                extra = inscode[27:32]
                op2_val = HalfPrecision.hpbin2dec(extra.zfill(Length.precision))
            elif rb == '1':
                op2_addr_bits = inscode[20:27]
                op2_mode = inscode[17:20]
                if op2_mode in ('000', '001', '010', '011'):
                    op2_val = AddressingMode.based(op2_addr_bits)
                else:
                    op2_val = AddressingMode.relative(op2_addr_bits)
            else:
                _, op2_val, _ = self.getOp(inscode[17:20], inscode[20:27], 2)

            jump_taken = False

            if exec_bit == '1':
                result = self.execute((op1_val, op2_val), opcode)
                if write_bit == '0':
                    if result:
                        register.store(pc_addr, op1_val)
                        register.store(ir_addr, op1_val)
                        jump_taken = True
            else:
                result = op2_val

            if write_bit == '1':
                movecode = self._get_movecode(opcode)
                self.write((op1_stor, op1_eff), result, movecode)

            if exec_bit == '0' and write_bit == '0':
                print(result)

            if not jump_taken:
                pc = register.load(pc_addr)
                register.store(ir_addr, pc)
                register.store(pc_addr, pc + 1)


if __name__ == "__main__":
    import os
    import sys

    REQUIRED_EXT = ".stepanmonster"

    def run_from_file(filename):
        if os.path.splitext(filename)[1].lower() != REQUIRED_EXT:
            raise ValueError(f"Input file must use the '{REQUIRED_EXT}' extension.")

        with open(filename, 'r') as f:
            instructions = f.readlines()

        # Required runtime exception variable for division-by-zero handling.
        divzero = Except("Division by zero")

        program = Program(instructions)
        program.run()
        return divzero

    filename = sys.argv[1] if len(sys.argv) > 1 else f"program{REQUIRED_EXT}"
    run_from_file(filename)
