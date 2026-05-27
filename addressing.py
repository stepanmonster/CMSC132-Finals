"""
Addressing modes and storage access for the CMSC132 ISA simulator.

Provides:
  - Access: thin wrapper to load/store values from memory or register
            by name or address, following a chain of indirections.
  - AddressingMode: static implementations of every addressing mode
            supported by the ISA (register, register-indirect, direct,
            indirect, indexed, auto-increment, auto-decrement, immediate,
            based, relative).

Dependencies: storage (memory, register, variable), bin_convert (HalfPrecision, Length)
"""

from storage import memory, register, variable
from bin_convert import HalfPrecision, Length


class Access:
    """Thin wrapper for reading from and writing to memory or registers."""

    @staticmethod
    def data(addr, flow):
        """Load a value by following a chain of storage indirections.

        Parameters
        ----------
        addr : str or int
            Starting address (looked up in the first element's storage).
        flow : list of str
            Each element is one of 'var', 'reg', or 'mem'.
            The value returned by one step becomes the address of the next.

        Example
        -------
        Access.data('PC', ['var', 'reg'])
          1. Look up 'PC' in variable  → gives a numeric address (e.g. 13)
          2. Look up  13 in register   → returns the value stored there

        Returns
        -------
        The value found in the storage named by the last element of flow.
        """
        current = addr
        storage_map = {'var': variable, 'reg': register, 'mem': memory}
        for step in flow:
            current = storage_map[step].load(current)
        return current

    @staticmethod
    def store(typ, addr, value):
        """Store *value* at *addr* inside the storage indicated by *typ*.

        Parameters
        ----------
        typ   : 'register' or 'memory'
        addr  : numeric address
        value : value to store (decimal or binary string)
        """
        if typ == 'register':
            register.store(addr, value)
        else:
            memory.store(addr, value)


# ---------------------------------------------------------------------------
# Addressing Modes
# ---------------------------------------------------------------------------

class AddressingMode:
    """Static implementations of every addressing mode in the ISA."""

    # ------------------------------------------------------------------
    # Modes that can appear on EITHER operand
    # ------------------------------------------------------------------

    @staticmethod
    def register(reg_addr):
        """Register addressing mode.

        Loads the value stored in the register at *reg_addr*.

        Parameters
        ----------
        reg_addr : int
            Numeric register address.

        Returns
        -------
        (effective_address, value, 'register')
        """
        eff = reg_addr
        val = register.load(eff)
        return (eff, val, 'register')

    @staticmethod
    def register_indirect(reg_addr):
        """Register-indirect addressing mode.

        The register holds a *memory* address; returns the value at that
        memory location.

        Parameters
        ----------
        reg_addr : int
            Numeric register address whose content is the memory address.

        Returns
        -------
        (effective_address, value)  — storage type is always 'memory'.
        """
        mem_addr = register.load(reg_addr)
        eff = mem_addr
        val = memory.load(eff)
        return (eff, val)

    @staticmethod
    def direct(var_addr):
        """Direct (absolute) addressing mode.

        *var_addr* is used directly as a memory address.

        Parameters
        ----------
        var_addr : int
            Numeric memory address.

        Returns
        -------
        (effective_address, value)
        """
        eff = var_addr
        val = memory.load(eff)
        return (eff, val)

    @staticmethod
    def indirect(var_addr):
        """Indirect addressing mode.

        The memory cell at *var_addr* holds the *actual* address to read.

        Parameters
        ----------
        var_addr : int
            Numeric address of the pointer cell in memory.

        Returns
        -------
        (effective_address, value)
        """
        ptr = memory.load(var_addr)
        eff = ptr
        val = memory.load(eff)
        return (eff, val)

    @staticmethod
    def indexed(addr_bits):
        """Indexed addressing mode.

        The 7-bit *addr_bits* field encodes both the displacement type
        (bit 0) and a 6-bit displacement value (bits 1-6).

        Bit 0 of addr_bits:
          '0' → displacement is a positive integer added to XR
          '1' → displacement is a negative integer added to XR

        The effective address = XR + displacement.

        Parameters
        ----------
        addr_bits : str
            7-bit binary string from the instruction word.

        Returns
        -------
        (effective_address, value)
        """
        sign_bit = addr_bits[0]
        disp = int(addr_bits[1:], 2)
        if sign_bit == '1':
            disp = -disp

        xr = Access.data('XR', ['var', 'reg'])
        eff = int(xr) + disp
        val = memory.load(eff)
        return (eff, val)

    @staticmethod
    def autoinc(reg_addr):
        """Auto-increment addressing mode.

        Reads the memory value pointed to by the register, then increments
        the register by 1 (post-increment).

        Parameters
        ----------
        reg_addr : int
            Numeric register address.

        Returns
        -------
        (effective_address, value)
        """
        mem_addr = register.load(reg_addr)
        eff = mem_addr
        val = memory.load(eff)
        # Post-increment the register
        register.store(reg_addr, mem_addr + 1)
        return (eff, val)

    @staticmethod
    def autodec(reg_addr):
        """Auto-decrement addressing mode.

        Decrements the register by 1 first (pre-decrement), then reads the
        memory value pointed to by the updated register.

        Parameters
        ----------
        reg_addr : int
            Numeric register address.

        Returns
        -------
        (effective_address, value)
        """
        mem_addr = register.load(reg_addr)
        # Pre-decrement the register
        new_addr = mem_addr - 1
        register.store(reg_addr, new_addr)
        eff = new_addr
        val = memory.load(eff)
        return (eff, val)

    # ------------------------------------------------------------------
    # Modes that are valid on the SECOND operand only
    # (rb bit must be 1, ib bit must be 0)
    # ------------------------------------------------------------------

    @staticmethod
    def immediate(var):
        """Immediate addressing mode.

        The operand value is encoded directly in the instruction word as a
        Half Precision binary string.

        Parameters
        ----------
        var : str
            Half Precision binary string (padded to Length.precision bits).

        Returns
        -------
        Decimal value decoded from the Half Precision format.
        """
        return HalfPrecision.hpbin2dec(var.zfill(Length.precision))

    @staticmethod
    def based(displace):
        """Based addressing mode.

        Effective address = BR (Based Register value) + displacement.
        Returns the value stored at the effective memory address.

        Parameters
        ----------
        displace : str
            7-bit binary string from the instruction word encoding the
            displacement (same sign/magnitude encoding as indexed).

        Returns
        -------
        Value stored at the effective address in memory.
        """
        sign_bit = displace[0]
        disp = int(displace[1:], 2)
        if sign_bit == '1':
            disp = -disp

        br = Access.data('BR', ['var', 'reg'])
        eff = int(br) + disp
        val = memory.load(eff)
        return val

    @staticmethod
    def relative(displace):
        """Relative addressing mode.

        Effective address = PC (Program Counter value) + displacement.
        Returns the value stored at the effective memory address.

        Parameters
        ----------
        displace : str
            7-bit binary string from the instruction word encoding the
            displacement (same sign/magnitude encoding as indexed).

        Returns
        -------
        Value stored at the effective address in memory.
        """
        sign_bit = displace[0]
        disp = int(displace[1:], 2)
        if sign_bit == '1':
            disp = -disp

        pc = Access.data('PC', ['var', 'reg'])
        eff = int(pc) + disp
        val = memory.load(eff)
        return val