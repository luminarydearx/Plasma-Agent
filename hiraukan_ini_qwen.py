nama = str(input("Masukkan nama anda: "))
umur = int(input("Masukkan umur anda: "))
hobi = str(input("Masukkan hobi anda: "))

# Pengkondisian kategori umur, anak, remaja, dewasa, lansia, dan pengkondisian agar tidak bisa memasukkan umur negatif

if umur < 12:
    kategori = "anak-anak"
elif umur < 18:
    kategori = "remaja"
elif umur < 60:
    kategori = "dewasa"
else:
    kategori = "lansia"    