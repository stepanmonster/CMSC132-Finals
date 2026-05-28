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
        """Encode each instruction of the program."""
        Instruction.encodeProgram(program)

    @staticmethod
    def exception(name, value):
        """Finds the exception based on its name and value.

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

    def getOp(self, inscode):
        """Gets the effective address and the type of storage (memory or register) of the operand.

        Parameters:
            inscode — the code of operand including addressing mode.

        Process:
            1. If the addressing mode is immediate, return its Half Precision decimal value.
            2. If it is based, indexed, or relative, identify the displacement.
            3. Otherwise, identify the storage (memory or register) address
               (make sure to get the Half Precision decimal value).
            4. Call the appropriate addressing mode with the appropriate parameter.

        Returns: The addressing mode except for immediate.
        """
        ib = inscode[5]       # immediate bit
        rb = inscode[16]      # relative/based bit
        mode_bits = inscode[17:20]   # Op2Mode
        addr_bits = inscode[20:27]   # Op2Addr

        # 1. Immediate addressing mode
        if ib == '1':
            extra = inscode[27:32]
            val = HalfPrecision.hpbin2dec(extra.zfill(Length.precision))
            return (None, val, None)

        # 2. Based, indexed, or relative — identify displacement type
        if rb == '1':
            if mode_bits in ('000', '001', '010', '011'):
                val = AddressingMode.based(addr_bits)
            else:
                val = AddressingMode.relative(addr_bits)
            return (None, val, 'memory')

        # 3. Otherwise — standard addressing modes
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
        """Perform Execute operations.

        Process: Get the category from the opcode.
        - If the Write Bit of the opcode is 1, perform the four basic operations
          and modulo based on the category and return the result. For division,
          create an exception for division by zero.
        - Otherwise (Write Bit of the opcode is 0), perform jumps based on the
          category. The purpose of jump with comparison is really to compare the
          'JR' and zero.

        Returns: The result if Write Bit of the opcode is 1.
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
        """Perform Write operations.

        dest = (storage_type, address) tuple
        movecode determines special write behavior:
        1 = CALL: move PC -> CR, then src -> dest
        2 = RET:  move CR -> PC, then src -> dest
        3 = SCAN: replace src with message value, then src -> dest
        any = default: always perform src -> dest
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
        """Execute each Instruction Codes starting from the address pointed by 'IR'.

        Process: Initialize a list of monadic and niladic operations. They are
        for future use but for now, it's empty because all operations are
        converted to instructions with two operands.

        Loop:
        1. Gets the value of 'IR'. Get the Instruction Code pointed by the 'IR'.
           If the Instruction Code is not a 32-bit format or consists of all
           zeros, break from the loop.
        2. Get the opcode, the first operand, and the second operand (only if
           the operation is not dyadic).
        3. If the Execute Bit is 1, perform the execute with appropriate
           parameters. If the Write Bit is 1, perform the write with appropriate
           parameters.
        4. If both the Execute and Write Bit are all zeros, perform the print.
        5. Move the value of 'PC' to 'IR', then increment the value of 'PC' by 1.
        """
        # Initialize a list of monadic and niladic operations.
        # For future use; currently empty because all operations are converted
        # to instructions with two operands.
        monadic_ops = []
        niladic_ops = []

        ir_addr = variable.data["IR"]
        pc_addr = variable.data["PC"]

        while True:
            # 1. Fetch — get IR value, load instruction code from memory
            ir = register.load(ir_addr)
            inscode = memory.load(ir)

            # If not 32-bit format or all zeros, break
            if not isinstance(inscode, str) or len(inscode) != Length.instrxn or inscode == "0" * Length.instrxn:
                break

            # 2. Decode — get opcode, first operand, second operand
            opcode = inscode[0:5]
            exec_bit = inscode[0]
            write_bit = inscode[1]

            # Resolve first operand (op1) — always standard addressing
            op1_mode = inscode[6:9]
            op1_addr = inscode[9:16]
            op1_addr_int = int(op1_addr, 2)

            if op1_mode == '000':
                op1_eff, op1_val, _ = AddressingMode.register(op1_addr_int)
                op1_stor = 'register'
            elif op1_mode == '001':
                op1_eff, op1_val = AddressingMode.register_indirect(op1_addr_int)
                op1_stor = 'memory'
            elif op1_mode == '010':
                op1_eff, op1_val = AddressingMode.direct(op1_addr_int)
                op1_stor = 'memory'
            elif op1_mode == '011':
                op1_eff, op1_val = AddressingMode.indirect(op1_addr_int)
                op1_stor = 'memory'
            elif op1_mode in ('100', '101'):
                op1_eff, op1_val = AddressingMode.indexed(op1_addr)
                op1_stor = 'memory'
            elif op1_mode == '110':
                op1_eff, op1_val = AddressingMode.autoinc(op1_addr_int)
                op1_stor = 'memory'
            elif op1_mode == '111':
                op1_eff, op1_val = AddressingMode.autodec(op1_addr_int)
                op1_stor = 'memory'
            else:
                op1_eff, op1_val, op1_stor = None, None, None

            # Resolve second operand (op2) via getOp (handles all modes)
            _, op2_val, _ = self.getOp(inscode)

            jump_taken = False

            # 3. If Execute Bit is 1, perform execute
            if exec_bit == '1':
                result = self.execute((op1_val, op2_val), opcode)
                if write_bit == '0':
                    # Jump operation — update PC if condition is met
                    if result:
                        register.store(pc_addr, op1_val)
                        register.store(ir_addr, op1_val)
                        jump_taken = True
            else:
                result = op2_val

            # If Write Bit is 1, perform write
            if write_bit == '1':
                # Determine movecode from opcode (CALL=1, RET=2, SCAN=3, default=0)
                if exec_bit == '0':
                    cat = opcode[2:5]
                    if cat == '001':
                        movecode = 1
                    elif cat == '010':
                        movecode = 2
                    elif cat == '011':
                        movecode = 3
                    else:
                        movecode = 0
                else:
                    movecode = 0
                self.write((op1_stor, op1_eff), result, movecode)

            # 4. If both Execute and Write Bit are all zeros, perform print
            if exec_bit == '0' and write_bit == '0':
                print(result)

            # 5. Move PC to IR, then increment PC by 1
            if not jump_taken:
                pc = register.load(pc_addr)
                register.store(ir_addr, pc)
                register.store(pc_addr, pc + 1)


if __name__ == "__main__":
    import os
    import sys

    REQUIRED_EXT = ".stepanmonster"

    def run_from_file(filename):
        # Create a variable for division by zero exception
        divzero = Except("Division by zero")

        # Access the file (must have extension matching group name)
        if os.path.splitext(filename)[1].lower() != REQUIRED_EXT:
            raise ValueError(f"Input file must use the '{REQUIRED_EXT}' extension.")

        with open(filename, 'r') as f:
            instructions = f.readlines()

        # Convert text from file as list of instructions and pass to Program class
        program = Program(instructions)
        program.run()
        return divzero

    filename = sys.argv[1] if len(sys.argv) > 1 else f"program{REQUIRED_EXT}"
    run_from_file(filename)
