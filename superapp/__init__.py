"""INNASLOT Super App — sotuvchilar uchun qo'shimcha modullar.

⚠️ ARXITEKTURA QOIDASI: bu paket slot band qilish yadrosidan TO'LIQ ajratilgan.
   • alohida jarayon (slot-superapp.service)
   • alohida DB fayli (superapp.db)
   • `services/`, `handlers/`, `slot_checker` ga HECH QACHON import qilmaydi

   Sabab: band qilish yadrosi 170+ mijozning jonli puli. Bu yerdagi hech qanday
   xato, yuk yoki qulash u yerga yetib bormasligi kerak.

   YAGONA bog'lanish nuqtasi — `credits.py` dagi kredit almashtirish
   (mavjud `database.consume_credit`). Undan boshqa hech narsa umumiy emas.
"""
