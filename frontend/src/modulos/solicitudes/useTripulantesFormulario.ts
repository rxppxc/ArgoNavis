/**
 * Las fichas de los tripulantes del formulario de solicitud y cuáles están
 * contraídas. Las funciones son estables: TarjetaTripulante está memoizada.
 */
import { useCallback, useState } from "react";
import type { RangoMarino, TripulanteEntrada } from "../../api/solicitudes";
import { fichaVacia } from "./envioSolicitud";
import type { FichaTripulante } from "./validacionFormulario";

export interface TripulantesFormulario {
  tripulantes: FichaTripulante[];
  /** Claves de las tarjetas contraídas. */
  contraidas: Set<string>;
  cambiar: (clave: string, campo: keyof TripulanteEntrada, valor: string) => void;
  /** Agrega una ficha vacía con el rango dado (el primero que admite el trámite). */
  agregar: (rango?: RangoMarino) => void;
  quitar: (clave: string) => void;
  /** Pasa al primero de `rangos` a quien tenga un rango que no está ahí (null = cualquiera). */
  ajustarRangos: (rangos: RangoMarino[] | null) => void;
  alternar: (clave: string) => void;
  /** Lleva a la tarjeta de un tripulante (la expande si estaba contraída). */
  irA: (clave: string) => void;
}

/** Sin fichas iniciales (solicitud nueva), empieza con una vacía. */
export function useTripulantesFormulario(iniciales: FichaTripulante[] = []): TripulantesFormulario {
  const [tripulantes, setTripulantes] = useState<FichaTripulante[]>(() => (iniciales.length ? iniciales : [fichaVacia()]));
  const [contraidas, setContraidas] = useState<Set<string>>(() => new Set());

  const cambiar = useCallback((clave: string, campo: keyof TripulanteEntrada, valor: string) => {
    setTripulantes((prev) => prev.map((t) => (t.clave === clave ? { ...t, [campo]: valor } : t)));
  }, []);

  const agregar = useCallback((rango?: RangoMarino) => {
    setTripulantes((prev) => [...prev, fichaVacia(rango)]);
  }, []);

  const quitar = useCallback((clave: string) => {
    setTripulantes((prev) => prev.filter((t) => t.clave !== clave));
  }, []);

  const ajustarRangos = useCallback((rangos: RangoMarino[] | null) => {
    if (!rangos?.length) return;
    setTripulantes((prev) => prev.map((t) => (rangos.includes(t.rango) ? t : { ...t, rango: rangos[0] })));
  }, []);

  const alternar = useCallback((clave: string) => {
    setContraidas((prev) => {
      const siguiente = new Set(prev);
      if (siguiente.has(clave)) siguiente.delete(clave); else siguiente.add(clave);
      return siguiente;
    });
  }, []);

  const irA = useCallback((clave: string) => {
    setContraidas((prev) => {
      const siguiente = new Set(prev);
      siguiente.delete(clave);
      return siguiente;
    });
    requestAnimationFrame(() => {
      document.getElementById(`tripulante-${clave}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, []);

  return { tripulantes, contraidas, cambiar, agregar, quitar, ajustarRangos, alternar, irA };
}
