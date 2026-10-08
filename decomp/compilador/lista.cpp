// Fase 1: caso de teste do compilador que ainda não virou arquivo de src/.
//
// 0x0202d428  lista dinâmica: remover o item da posição idx (Thumb, 0x2c bytes)
//
// {int count; int capacidade; T* data} com T de 4 bytes feito de dois u16.
// O assembly relê `data` e `count` a cada volta do laço: o compilador não pode
// provar que gravar em data[i] não muda o próprio objeto.
//
// É esta função que separa as versões: o mwccarm "DSi" (4.0) aloca os
// registradores de outro jeito e erra 16 instruções. Ainda não sabemos o nome
// da classe (é um template, usado com vários tipos), por isso fica aqui.
struct Par16 {
    unsigned short a, b;
};

template <class T>
struct Lista {
    int count;      // +0x0
    int capacity;   // +0x4
    T* data;        // +0x8
    void RemoveAt(int idx)
    {
        count--;
        for (int i = idx; i < count; i++)
            data[i] = data[i + 1];
    }
};

void Lista_Par16_RemoveAt(Lista<Par16>* lista, int idx)
{
    lista->RemoveAt(idx);
}
